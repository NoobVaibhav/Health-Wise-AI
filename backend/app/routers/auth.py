"""Login, current user, password change, and one-time creation of the first administrator."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database.connection import get_db
from app.database.models import AuditLog, User, utcnow
from app.schemas.auth import (
    ChangePasswordRequest, FirstAdminRequest, LoginRequest, TokenResponse, UserOut,
)
from app.services import audit_service, user_service
from app.services.profile_service import avatar_version

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role,
                   is_active=user.is_active, must_change_password=user.must_change_password,
                   has_avatar=bool(user.avatar_path), avatar_version=avatar_version(user))


@router.get("/setup-status")
def setup_status(db: Session = Depends(get_db)):
    """True on a brand new system with no users: the frontend then shows the 'create first admin' page."""
    return {"needs_setup": (db.scalar(select(func.count(User.id))) or 0) == 0}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_first_admin(data: FirstAdminRequest, request: Request, db: Session = Depends(get_db)):
    """Public registration is closed in a hospital system. This works ONLY while there are no users at all."""
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Registration is closed. Accounts are created by hospital staff.")
    admin = user_service.create_admin(db, data.email, data.full_name, data.password)
    audit_service.log_action(db, admin, audit_service.USER_CREATED, "user", admin.id, request, "first admin")
    return TokenResponse(access_token=create_access_token(admin.id, admin.password_hash), user=user_out(admin))


LOCK_MINUTES = 15
MAX_FAILS_PER_EMAIL = 5
MAX_FAILS_PER_IP = 30


def _too_many_failures(db: Session, email: str, ip: str | None) -> bool:
    """Brute-force guard: counts recent failed logins in the audit log (so it survives restarts and several workers)."""
    since = utcnow() - timedelta(minutes=LOCK_MINUTES)
    base = select(func.count(AuditLog.id)).where(AuditLog.action == audit_service.LOGIN_FAILED, AuditLog.timestamp >= since)
    if (db.scalar(base.where(AuditLog.details == email)) or 0) >= MAX_FAILS_PER_EMAIL:
        return True
    return bool(ip) and (db.scalar(base.where(AuditLog.ip_address == ip)) or 0) >= MAX_FAILS_PER_IP


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    if _too_many_failures(db, email, request.client.host if request.client else None):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many failed attempts. Please wait {LOCK_MINUTES} minutes and try again.")
    user = db.scalar(select(User).where(User.email == email))
    # Same message for unknown email and wrong password, so attackers cannot find out which emails exist.
    if not user or not verify_password(data.password, user.password_hash):
        audit_service.log_action(db, user, audit_service.LOGIN_FAILED, "user", user.id if user else None, request,
                                 data.email.lower())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated. Please contact the admin.")
    audit_service.log_action(db, user, audit_service.LOGIN, "user", user.id, request)
    return TokenResponse(access_token=create_access_token(user.id, user.password_hash), user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/change-password")
def change_password(data: ChangePasswordRequest, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The new password must be different from the current one.")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    db.commit()
    audit_service.log_action(db, user, "PASSWORD_CHANGED", "user", user.id, request)
    # every older token stops working; this device gets a new one so the user stays signed in
    return {"message": "Password changed.", "access_token": create_access_token(user.id, user.password_hash)}

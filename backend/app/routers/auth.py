"""Login, current user, password change, and one-time creation of the first administrator."""
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import get_current_user
from app.core.security import create_access_token, hash_password, is_current_hash, verify_password
from app.database.connection import get_db
from app.database.models import AuditLog, User, utcnow
from app.schemas.auth import (
    ChangePasswordRequest, FirstAdminRequest, LoginRequest, OtpRequest, OtpVerify, TokenResponse, UserOut,
)
from app.services import audit_service, otp_service, user_service
from app.services.profile_service import avatar_version
from app.utils.validators import NO_NAME_IN_PASSWORD, password_has_email_name

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(user: User, db: Session | None = None, with_permissions: bool = False) -> UserOut:
    grade = None
    if user.role == "DOCTOR":                          # the menu and the workspace follow the grade
        from sqlalchemy.orm import object_session
        from app.database.models import Doctor
        session = db or object_session(user)
        grade = (session.scalar(select(Doctor.grade).where(Doctor.user_id == user.id)) if session is not None else None) or "CONSULTANT"
    staff_type = None
    if user.role in ("LAB", "RADIOLOGY"):
        from sqlalchemy.orm import object_session
        from app.database.models import LabStaff, RadiologyStaff
        session = db or object_session(user)
        model = LabStaff if user.role == "LAB" else RadiologyStaff
        staff_type = (session.scalar(select(model.staff_type).where(model.user_id == user.id)) if session is not None else None) or "TECHNICIAN"
    permissions = []
    if with_permissions and user.role != "PATIENT":
        from sqlalchemy.orm import object_session
        from app.services.access_service import permissions_of
        session = db or object_session(user)
        permissions = sorted(permissions_of(session, user)) if session is not None else []
    return UserOut(id=user.id, staff_type=staff_type, permissions=permissions, email=user.email, full_name=user.full_name, role=user.role,
                   is_active=user.is_active, must_change_password=user.must_change_password,
                   has_avatar=bool(user.avatar_path), avatar_version=avatar_version(user), grade=grade)


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
MAX_FAILS_PER_EMAIL_AND_IP = 5       # one person typing a wrong password again and again from one place
MAX_FAILS_PER_EMAIL = 30             # the same account attacked from many places
MAX_FAILS_PER_IP = 30                # one place trying many accounts


def minutes_until_unlocked(db: Session, email: str, ip: str | None) -> int:
    """0 when the login may be tried, else the number of minutes to wait. Counts recent failed logins in the audit log (so it survives restarts
    and several workers). The lock is per e-mail AND address: somebody else typing wrong passwords for your e-mail from another place cannot lock YOU out."""
    since = utcnow() - timedelta(minutes=LOCK_MINUTES)
    base = select(AuditLog.timestamp).where(AuditLog.action == audit_service.LOGIN_FAILED, AuditLog.timestamp >= since)
    checks = [(base.where(AuditLog.details == email, AuditLog.ip_address == ip) if ip else base.where(AuditLog.details == email), MAX_FAILS_PER_EMAIL_AND_IP),
              (base.where(AuditLog.details == email), MAX_FAILS_PER_EMAIL)]
    if ip:
        checks.append((base.where(AuditLog.ip_address == ip), MAX_FAILS_PER_IP))
    wait = 0
    for query, limit in checks:
        times = sorted(db.scalars(query.order_by(AuditLog.timestamp)))
        if len(times) >= limit:
            unlock = times[len(times) - limit] + timedelta(minutes=LOCK_MINUTES)       # when the failure that made it "too many" leaves the window
            wait = max(wait, math.ceil((unlock - utcnow()).total_seconds() / 60))
    return max(wait, 1) if wait > 0 else 0


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    wait = minutes_until_unlocked(db, email, request.client.host if request.client else None)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many failed attempts. Please try again in {wait} minute{'s' if wait != 1 else ''}.",
                            headers={"Retry-After": str(wait * 60)})
    user = db.scalar(select(User).where(User.email == email))
    # Same message for unknown email and wrong password, so attackers cannot find out which emails exist.
    if not user or not verify_password(data.password, user.password_hash):
        audit_service.log_action(db, user, audit_service.LOGIN_FAILED, "user", user.id if user else None, request,
                                 data.email.lower())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated. Please contact the admin.")
    if not is_current_hash(user.password_hash):          # an older password record: save it again in the stronger form
        user.password_hash = hash_password(data.password)
        db.commit()
    audit_service.log_action(db, user, audit_service.LOGIN, "user", user.id, request)
    return TokenResponse(access_token=create_access_token(user.id, user.password_hash), user=user_out(user, with_permissions=True))


@router.post("/otp/request")
def otp_request(data: OtpRequest, request: Request, db: Session = Depends(get_db)):
    """Ask for a sign-in code for a mobile number. The answer is the same whether or not the number is registered."""
    return otp_service.request_code(db, data.phone, request.client.host if request.client else None)


@router.post("/otp/verify", response_model=TokenResponse)
def otp_verify(data: OtpVerify, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    user = None
    try:
        user = otp_service.users_with_phone(db, otp_service.clean_phone(data.phone))
        user = user[0] if len(user) == 1 else None
        if user is not None:
            wait = minutes_until_unlocked(db, user.email, ip)
            if wait:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many failed attempts. Please try again in {wait} minute{'s' if wait != 1 else ''}.", headers={"Retry-After": str(wait * 60)})
        user = otp_service.verify_code(db, data.phone, data.code)
    except HTTPException as e:
        if e.status_code == 401:
            audit_service.log_action(db, user, audit_service.LOGIN_FAILED, "user", user.id if user else None, request, "mobile code")
        raise
    audit_service.log_action(db, user, audit_service.LOGIN, "user", user.id, request, "mobile code")
    return TokenResponse(access_token=create_access_token(user.id, user.password_hash), user=user_out(user, with_permissions=True))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user, with_permissions=True)


@router.post("/change-password")
def change_password(data: ChangePasswordRequest, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The new password must be different from the current one.")
    if data.new_password == get_settings().default_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please choose your own password, not the starting password.")
    if password_has_email_name(data.new_password, user.email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422, NO_NAME_IN_PASSWORD)
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    db.commit()
    audit_service.log_action(db, user, "PASSWORD_CHANGED", "user", user.id, request)
    # every older token stops working; this device gets a new one so the user stays signed in
    return {"message": "Password changed.", "access_token": create_access_token(user.id, user.password_hash)}

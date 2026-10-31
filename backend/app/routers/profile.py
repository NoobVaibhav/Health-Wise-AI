"""My profile (every role): details, editable fields and the profile picture."""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.permissions import forbidden, get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services import audit_service, profile_service
from app.utils.validators import PathId

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.get_profile(db, user)


@router.put("", response_model=ProfileOut)
def update_my_profile(data: ProfileUpdate, request: Request, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    result = profile_service.update_profile(db, user, data)
    audit_service.log_action(db, user, audit_service.PROFILE_UPDATED, "user", user.id, request)
    return result


@router.post("/avatar", response_model=ProfileOut)
async def upload_avatar(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    content = await file.read(profile_service.MAX_AVATAR_BYTES + 1)
    profile_service.set_avatar(db, user, content)
    audit_service.log_action(db, user, audit_service.AVATAR_CHANGED, "user", user.id, request, "photo added")
    return profile_service.get_profile(db, user)


@router.delete("/avatar", response_model=ProfileOut)
def delete_avatar(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile_service.remove_avatar(db, user)
    audit_service.log_action(db, user, audit_service.AVATAR_CHANGED, "user", user.id, request, "photo removed")
    return profile_service.get_profile(db, user)


@router.get("/avatar/{user_id}")
def get_avatar(user_id: PathId, viewer: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The picture file. Sent only to people allowed to see it, and only through this authorised call."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture.")
    if not profile_service.may_view_avatar(viewer, target):
        raise forbidden()
    path = profile_service.avatar_file(target)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})

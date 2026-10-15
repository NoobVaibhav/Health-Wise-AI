from datetime import datetime

from pydantic import BaseModel, Field


class ProfileField(BaseModel):
    key: str
    label: str
    kind: str                       # text | textarea | number | date
    value: str | int | None
    editable: bool
    help: str | None = None


class ProfileUser(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    role_label: str
    created_at: datetime
    last_login: datetime | None
    has_avatar: bool
    avatar_version: str | None


class ProfileOut(BaseModel):
    user: ProfileUser
    fields: list[ProfileField]


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    values: dict[str, str | int | None] = Field(default_factory=dict)

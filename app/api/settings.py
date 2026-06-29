import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.models.settings import UserSettings
from app.models.user import User

router = APIRouter()

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class SettingsResponse(BaseModel):
    autoOpenReflection: bool
    preferredFocusTime: str
    maxSessionsPerDay: int
    timezone: str


class UpdateSettingsRequest(BaseModel):
    autoOpenReflection: Optional[bool] = Field(default=None)
    preferredFocusTime: Optional[str] = Field(default=None, max_length=5)
    maxSessionsPerDay: Optional[int] = Field(default=None, ge=1, le=20)
    timezone: Optional[str] = Field(default=None, max_length=50)

    @field_validator("preferredFocusTime")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not TIME_RE.match(value):
            raise ValueError("Time must be in HH:MM format (00:00-23:59).")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("Timezone must not be empty.")
        return value.strip()


def _raise(code: str, message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=api_error(code, message))


def _settings_response(s: UserSettings) -> SettingsResponse:
    return SettingsResponse(
        autoOpenReflection=s.auto_open_reflection,
        preferredFocusTime=s.preferred_focus_time,
        maxSessionsPerDay=s.max_sessions_per_day,
        timezone=s.timezone,
    )


def _ensure_settings(user: User, db: Session) -> UserSettings:
    settings = db.get(UserSettings, user.id)
    if settings is not None:
        return settings
    settings = UserSettings(id=user.id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    settings = _ensure_settings(user, db)
    return _settings_response(settings)


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(
    payload: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    settings = _ensure_settings(user, db)
    changed = False
    if payload.autoOpenReflection is not None:
        settings.auto_open_reflection = payload.autoOpenReflection
        changed = True
    if payload.preferredFocusTime is not None:
        settings.preferred_focus_time = payload.preferredFocusTime
        changed = True
    if payload.maxSessionsPerDay is not None:
        settings.max_sessions_per_day = payload.maxSessionsPerDay
        changed = True
    if payload.timezone is not None:
        settings.timezone = payload.timezone
        changed = True
    if changed:
        settings.updated_at = datetime.now()
        db.commit()
        db.refresh(settings)
    return _settings_response(settings)

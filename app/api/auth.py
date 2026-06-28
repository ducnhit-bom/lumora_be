from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import api_error
from app.core.security import create_token, hash_password, hash_token, session_expiry, verify_password
from app.models.user import AuthSession, User

router = APIRouter()


class AuthUser(BaseModel):
    id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    accessToken: str
    user: AuthUser


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _raise(code: str, message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=api_error(code, message))


def _response(user: User, db: Session) -> AuthResponse:
    token = create_token()
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=session_expiry()))
    db.commit()
    return AuthResponse(accessToken=token, user=AuthUser(id=user.id, name=user.name, email=user.email))


def get_current_session(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not authorization or not authorization.startswith("Bearer "):
        _raise("missing_token", "Missing bearer token.", status.HTTP_401_UNAUTHORIZED)

    token = authorization.removeprefix("Bearer ").strip()
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    now = datetime.now(timezone.utc)
    if not session:
        _raise("invalid_token", "Invalid or expired token.", status.HTTP_401_UNAUTHORIZED)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if session.revoked_at is not None or expires_at <= now:
        _raise("invalid_token", "Invalid or expired token.", status.HTTP_401_UNAUTHORIZED)
    return session


def get_current_user(session: AuthSession = Depends(get_current_session)) -> User:
    return session.user


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        _raise("duplicate_email", "Email is already registered.", status.HTTP_409_CONFLICT)

    user = User(name=payload.name.strip(), email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _raise("duplicate_email", "Email is already registered.", status.HTTP_409_CONFLICT)
    db.refresh(user)
    return _response(user, db)


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password):
        _raise("bad_credentials", "Email or password is incorrect.", status.HTTP_401_UNAUTHORIZED)
    return _response(user, db)


@router.post("/auth/logout")
def logout(session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)) -> dict[str, str]:
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}


@router.get("/users/me", response_model=AuthUser)
def me(user: User = Depends(get_current_user)) -> AuthUser:
    return AuthUser(id=user.id, name=user.name, email=user.email)

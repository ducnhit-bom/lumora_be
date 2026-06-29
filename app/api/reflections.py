from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.models.journey import FocusSession, Reflection, WeeklyJourney
from app.models.user import User

router = APIRouter()

MOODS = {"energized", "balanced", "challenged"}
FALLBACK_QUESTION = "What did this focus session teach you about your next calm step?"


class ReflectionQuestionResponse(BaseModel):
    sessionId: str
    question: str


class CreateReflectionRequest(BaseModel):
    sessionId: str
    content: str = Field(min_length=1, max_length=500)
    mood: Optional[str] = Field(default=None, max_length=20)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reflection content is required.")
        return value

    @field_validator("mood")
    @classmethod
    def mood_must_be_known(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in MOODS:
            raise ValueError("Mood must be energized, balanced, or challenged.")
        return normalized


class ReflectionResponse(BaseModel):
    id: str
    journeyId: str
    sessionId: str
    content: str
    mood: Optional[str]
    createdAt: datetime


class ReflectionListResponse(BaseModel):
    reflections: list[ReflectionResponse]


def _raise(code: str, message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=api_error(code, message))


def _owned_session(session_id: str, user: User, db: Session) -> FocusSession:
    session = db.get(FocusSession, session_id)
    if not session or session.user_id != user.id:
        _raise("not_found", "Session was not found.", status.HTTP_404_NOT_FOUND)
    return session


def _owned_journey(journey_id: str, user: User, db: Session) -> WeeklyJourney:
    journey = db.get(WeeklyJourney, journey_id)
    if not journey or journey.user_id != user.id:
        _raise("not_found", "Journey was not found.", status.HTTP_404_NOT_FOUND)
    return journey


def _reflection_response(reflection: Reflection) -> ReflectionResponse:
    return ReflectionResponse(
        id=reflection.id,
        journeyId=reflection.journey_id,
        sessionId=reflection.session_id,
        content=reflection.content,
        mood=reflection.mood,
        createdAt=reflection.created_at,
    )


@router.get("/sessions/{session_id}/reflection-question", response_model=ReflectionQuestionResponse)
def reflection_question(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReflectionQuestionResponse:
    session = _owned_session(session_id, user, db)
    return ReflectionQuestionResponse(sessionId=session.id, question=FALLBACK_QUESTION)


@router.post("/reflections", response_model=ReflectionResponse)
def create_reflection(payload: CreateReflectionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReflectionResponse:
    session = _owned_session(payload.sessionId, user, db)
    if session.status != "completed":
        _raise("invalid_state", "Only completed sessions can be reflected on.", status.HTTP_400_BAD_REQUEST)
    reflection = Reflection(
        user_id=user.id,
        journey_id=session.journey_id,
        session_id=session.id,
        content=payload.content.strip(),
        mood=payload.mood,
    )
    db.add(reflection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _raise("duplicate_reflection", "Reflection already exists for this session.", status.HTTP_409_CONFLICT)
    db.refresh(reflection)
    return _reflection_response(reflection)


@router.get("/journeys/{journey_id}/reflections", response_model=ReflectionListResponse)
def journey_reflections(journey_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReflectionListResponse:
    journey = _owned_journey(journey_id, user, db)
    reflections = list(
        db.scalars(
            select(Reflection)
            .where(Reflection.user_id == user.id, Reflection.journey_id == journey.id)
            .order_by(Reflection.created_at.asc(), Reflection.id.asc())
        )
    )
    return ReflectionListResponse(reflections=[_reflection_response(reflection) for reflection in reflections])

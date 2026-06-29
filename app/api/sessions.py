from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.models.journey import FocusSession, WeeklyJourney
from app.models.user import User

router = APIRouter()


class SessionResponse(BaseModel):
    id: str
    journeyId: str
    title: str
    note: Optional[str]
    category: str
    priority: str
    estimatedMinutes: int
    scheduledDate: Optional[date]
    scheduledTime: Optional[str]
    status: str
    completedAt: Optional[datetime]
    skippedAt: Optional[datetime]


class TodayResponse(BaseModel):
    date: date
    sessions: list[SessionResponse]


class CompleteResponse(BaseModel):
    sessionId: str
    status: str
    completedAt: datetime
    openReflection: bool


class UndoCompleteResponse(BaseModel):
    sessionId: str
    status: str
    completedAt: None


class SkipResponse(BaseModel):
    sessionId: str
    status: str
    skippedAt: datetime


def _raise(code: str, message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=api_error(code, message))


def _owned_session(session_id: str, user: User, db: Session) -> FocusSession:
    session = db.get(FocusSession, session_id)
    if not session or session.user_id != user.id:
        _raise("not_found", "Session was not found.", status.HTTP_404_NOT_FOUND)
    return session


def _session_response(session: FocusSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        journeyId=session.journey_id,
        title=session.title,
        note=session.note,
        category=session.category,
        priority=session.priority,
        estimatedMinutes=session.estimated_minutes,
        scheduledDate=session.scheduled_date,
        scheduledTime=session.scheduled_time,
        status=session.status,
        completedAt=session.completed_at,
        skippedAt=session.skipped_at,
    )


@router.get("/sessions/today", response_model=TodayResponse)
def today_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TodayResponse:
    today = date.today()
    sessions = list(
        db.scalars(
            select(FocusSession)
            .join(WeeklyJourney, FocusSession.journey_id == WeeklyJourney.id)
            .where(FocusSession.user_id == user.id, FocusSession.scheduled_date == today)
            .where(WeeklyJourney.status == "active")
            .order_by(FocusSession.scheduled_time.asc(), FocusSession.created_at.asc())
        )
    )
    return TodayResponse(date=today, sessions=[_session_response(session) for session in sessions])


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def session_detail(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SessionResponse:
    return _session_response(_owned_session(session_id, user, db))


@router.post("/sessions/{session_id}/complete", response_model=CompleteResponse)
def complete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CompleteResponse:
    session = _owned_session(session_id, user, db)
    if session.status != "scheduled":
        _raise("invalid_state", "Only scheduled sessions can be completed.", status.HTTP_400_BAD_REQUEST)
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(FocusSession)
        .where(FocusSession.id == session.id, FocusSession.user_id == user.id, FocusSession.status == "scheduled")
        .values(status="completed", completed_at=now, skipped_at=None)
    )
    if result.rowcount != 1:
        db.rollback()
        _raise("invalid_state", "Only scheduled sessions can be completed.", status.HTTP_400_BAD_REQUEST)
    db.commit()
    db.refresh(session)
    return CompleteResponse(sessionId=session.id, status=session.status, completedAt=session.completed_at, openReflection=True)


@router.post("/sessions/{session_id}/undo-complete", response_model=UndoCompleteResponse)
def undo_complete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UndoCompleteResponse:
    session = _owned_session(session_id, user, db)
    if session.status != "completed":
        _raise("invalid_state", "Only completed sessions can be restored.", status.HTTP_400_BAD_REQUEST)
    session.status = "scheduled"
    session.completed_at = None
    db.commit()
    return UndoCompleteResponse(sessionId=session.id, status=session.status, completedAt=None)


@router.post("/sessions/{session_id}/skip", response_model=SkipResponse)
def skip_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SkipResponse:
    session = _owned_session(session_id, user, db)
    if session.status != "scheduled":
        _raise("invalid_state", "Only scheduled sessions can be skipped.", status.HTTP_400_BAD_REQUEST)
    now = datetime.now(timezone.utc)
    session.status = "skipped"
    session.skipped_at = now
    session.completed_at = None
    db.commit()
    db.refresh(session)
    return SkipResponse(sessionId=session.id, status=session.status, skippedAt=session.skipped_at)

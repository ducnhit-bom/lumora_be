from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.models.journey import FocusSession, WeeklyJourney
from app.models.user import User

router = APIRouter()

PRIORITIES = {"low", "medium", "high"}
STATUSES_MUTABLE = {"draft"}


class CreateJourneyRequest(BaseModel):
    weekStart: date
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title is required.")
        return value


class AddSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    note: Optional[str] = Field(default=None, max_length=1000)
    category: str = Field(min_length=1, max_length=40)
    priority: str = Field(min_length=1, max_length=20)
    estimatedMinutes: int = Field(gt=0, le=480)

    @field_validator("title", "category", "priority")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value is required.")
        return value

    @field_validator("priority")
    @classmethod
    def priority_must_be_known(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PRIORITIES:
            raise ValueError("Priority must be low, medium, or high.")
        return normalized


class AcceptSessionRequest(BaseModel):
    sessionId: str
    suggestedTime: str


class AcceptDayRequest(BaseModel):
    date: date
    sessions: list[AcceptSessionRequest]


class AcceptJourneyRequest(BaseModel):
    days: list[AcceptDayRequest]


class JourneySessionResponse(BaseModel):
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


class JourneyResponse(BaseModel):
    id: str
    weekStart: date
    status: str
    title: str
    acceptedAt: Optional[datetime] = None
    sessions: list[JourneySessionResponse] = Field(default_factory=list)


class EmptyJourneyResponse(BaseModel):
    journey: None


class SuggestedSession(BaseModel):
    sessionId: str
    suggestedTime: str
    reason: str


class SuggestedDay(BaseModel):
    date: date
    sessions: list[SuggestedSession]


class SuggestResponse(BaseModel):
    source: str
    days: list[SuggestedDay]


class AcceptResponse(BaseModel):
    id: str
    status: str
    acceptedAt: datetime


def _raise(code: str, message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=api_error(code, message))


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _journey_response(journey: WeeklyJourney) -> JourneyResponse:
    sessions = sorted(journey.sessions, key=lambda item: item.created_at)
    return JourneyResponse(
        id=journey.id,
        weekStart=journey.week_start,
        status=journey.status,
        title=journey.title,
        acceptedAt=journey.accepted_at,
        sessions=[_session_response(session) for session in sessions],
    )


def _session_response(session: FocusSession) -> JourneySessionResponse:
    return JourneySessionResponse(
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
    )


def _owned_journey(journey_id: str, user: User, db: Session) -> WeeklyJourney:
    journey = db.get(WeeklyJourney, journey_id)
    if not journey or journey.user_id != user.id:
        _raise("not_found", "Journey was not found.", status.HTTP_404_NOT_FOUND)
    return journey


def _ensure_draft(journey: WeeklyJourney) -> None:
    if journey.status not in STATUSES_MUTABLE:
        _raise("invalid_state", "Only draft journeys can be changed.", status.HTTP_400_BAD_REQUEST)


def _fallback_schedule(journey: WeeklyJourney) -> SuggestResponse:
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    times = {"high": "09:00", "medium": "10:30", "low": "14:00"}
    sessions = sorted(journey.sessions, key=lambda item: (priority_rank.get(item.priority, 3), item.created_at))
    days: dict[date, list[SuggestedSession]] = {}
    for index, session in enumerate(sessions):
        scheduled_date = journey.week_start + timedelta(days=index % 7)
        days.setdefault(scheduled_date, []).append(
            SuggestedSession(
                sessionId=session.id,
                suggestedTime=times.get(session.priority, "10:30"),
                reason=_reason(session.priority),
            )
        )
    return SuggestResponse(source="fallback", days=[SuggestedDay(date=day, sessions=items) for day, items in days.items()])


def _reason(priority: str) -> str:
    if priority == "high":
        return "Start with high-focus work while energy is fresh."
    if priority == "medium":
        return "Keep steady progress in a focused mid-morning block."
    return "Place lighter work later so the week stays calm."


def _parse_time(value: str) -> str:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
    return parsed.strftime("%H:%M")


@router.post("/journeys", response_model=JourneyResponse)
def create_journey(payload: CreateJourneyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> JourneyResponse:
    journey = WeeklyJourney(user_id=user.id, week_start=_week_start(payload.weekStart), title=payload.title.strip(), status="draft")
    db.add(journey)
    db.commit()
    db.refresh(journey)
    return _journey_response(journey)


@router.get("/journeys/current", response_model=Union[JourneyResponse, EmptyJourneyResponse])
def current_journey(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Union[JourneyResponse, dict[str, None]]:
    current_week = _week_start(date.today())
    active = db.scalar(
        select(WeeklyJourney)
        .where(WeeklyJourney.user_id == user.id, WeeklyJourney.week_start == current_week, WeeklyJourney.status == "active")
        .order_by(WeeklyJourney.accepted_at.desc(), WeeklyJourney.id.desc())
    )
    if active:
        return _journey_response(active)
    draft = db.scalar(
        select(WeeklyJourney)
        .where(WeeklyJourney.user_id == user.id, WeeklyJourney.week_start == current_week, WeeklyJourney.status == "draft")
        .order_by(WeeklyJourney.created_at.desc(), WeeklyJourney.id.desc())
    )
    if draft:
        return _journey_response(draft)
    return {"journey": None}


@router.post("/journeys/{journey_id}/sessions", response_model=JourneySessionResponse)
def add_session(
    journey_id: str,
    payload: AddSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JourneySessionResponse:
    journey = _owned_journey(journey_id, user, db)
    _ensure_draft(journey)
    session = FocusSession(
        user_id=user.id,
        journey_id=journey.id,
        title=payload.title.strip(),
        note=payload.note.strip() if payload.note and payload.note.strip() else None,
        category=payload.category.strip().lower(),
        priority=payload.priority,
        estimated_minutes=payload.estimatedMinutes,
        status="todo",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_response(session)


@router.post("/journeys/{journey_id}/suggest", response_model=SuggestResponse)
def suggest_journey(journey_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SuggestResponse:
    journey = _owned_journey(journey_id, user, db)
    _ensure_draft(journey)
    if not journey.sessions:
        _raise("empty_journey", "Add at least one focus session first.", status.HTTP_400_BAD_REQUEST)
    return _fallback_schedule(journey)


@router.post("/journeys/{journey_id}/accept", response_model=AcceptResponse)
def accept_journey(
    journey_id: str,
    payload: AcceptJourneyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcceptResponse:
    journey = _owned_journey(journey_id, user, db)
    _ensure_draft(journey)
    assignments = _validated_assignments(journey, payload)
    for active in db.scalars(
        select(WeeklyJourney).where(
            WeeklyJourney.user_id == user.id,
            WeeklyJourney.week_start == journey.week_start,
            WeeklyJourney.status == "active",
            WeeklyJourney.id != journey.id,
        )
    ):
        active.status = "archived"
    for session_id, scheduled_date, scheduled_time in assignments:
        session = db.get(FocusSession, session_id)
        session.scheduled_date = scheduled_date
        session.scheduled_time = scheduled_time
        session.status = "scheduled"
    journey.status = "active"
    journey.accepted_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _raise("active_journey_conflict", "Another journey is already active for this week.", status.HTTP_409_CONFLICT)
    db.refresh(journey)
    return AcceptResponse(id=journey.id, status=journey.status, acceptedAt=journey.accepted_at)


def _validated_assignments(journey: WeeklyJourney, payload: AcceptJourneyRequest) -> list[tuple[str, date, str]]:
    if not payload.days:
        _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
    session_ids = {session.id for session in journey.sessions}
    seen: set[str] = set()
    assignments: list[tuple[str, date, str]] = []
    week_end = journey.week_start + timedelta(days=6)
    for day in payload.days:
        if day.date < journey.week_start or day.date > week_end or not day.sessions:
            _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
        for item in day.sessions:
            if item.sessionId in seen or item.sessionId not in session_ids:
                _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
            seen.add(item.sessionId)
            assignments.append((item.sessionId, day.date, _parse_time(item.suggestedTime)))
    if not assignments:
        _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
    if seen != session_ids:
        _raise("invalid_schedule", "Suggested schedule is invalid.", status.HTTP_400_BAD_REQUEST)
    return assignments

from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _id() -> str:
    return str(uuid4())


class WeeklyJourney(Base):
    __tablename__ = "weekly_journeys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="draft")
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["FocusSession"]] = relationship(back_populates="journey", cascade="all, delete-orphan")
    reflections: Mapped[list["Reflection"]] = relationship(back_populates="journey", cascade="all, delete-orphan")


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    journey_id: Mapped[str] = mapped_column(ForeignKey("weekly_journeys.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    scheduled_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="todo")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )

    journey: Mapped[WeeklyJourney] = relationship(back_populates="sessions")
    reflection: Mapped[Optional["Reflection"]] = relationship(back_populates="session")


class Reflection(Base):
    __tablename__ = "reflections"
    __table_args__ = (UniqueConstraint("session_id", name="uq_reflections_session_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    journey_id: Mapped[str] = mapped_column(ForeignKey("weekly_journeys.id"), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("focus_sessions.id"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mood: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )

    journey: Mapped[WeeklyJourney] = relationship(back_populates="reflections")
    session: Mapped[FocusSession] = relationship(back_populates="reflection")

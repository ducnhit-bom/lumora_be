from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), primary_key=True
    )
    auto_open_reflection: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    preferred_focus_time: Mapped[str] = mapped_column(
        String(5), default="09:00", nullable=False
    )
    max_sessions_per_day: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(50), default="Asia/Ho_Chi_Minh", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

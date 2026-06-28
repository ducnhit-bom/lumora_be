"""weekly journeys and focus sessions

Revision ID: 20260628_0003
Revises: 20260627_0002
Create Date: 2026-06-28
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260628_0003"
down_revision: Optional[str] = "20260627_0002"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "weekly_journeys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_weekly_journeys_status"), "weekly_journeys", ["status"], unique=False)
    op.create_index(op.f("ix_weekly_journeys_user_id"), "weekly_journeys", ["user_id"], unique=False)
    op.create_index(op.f("ix_weekly_journeys_week_start"), "weekly_journeys", ["week_start"], unique=False)
    op.create_index(
        "uq_weekly_journeys_one_active_per_week",
        "weekly_journeys",
        ["user_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "focus_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("journey_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("scheduled_time", sa.String(length=5), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["journey_id"], ["weekly_journeys.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_focus_sessions_journey_id"), "focus_sessions", ["journey_id"], unique=False)
    op.create_index(op.f("ix_focus_sessions_status"), "focus_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_focus_sessions_user_id"), "focus_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_focus_sessions_user_id"), table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_status"), table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_journey_id"), table_name="focus_sessions")
    op.drop_table("focus_sessions")
    op.drop_index("uq_weekly_journeys_one_active_per_week", table_name="weekly_journeys")
    op.drop_index(op.f("ix_weekly_journeys_week_start"), table_name="weekly_journeys")
    op.drop_index(op.f("ix_weekly_journeys_user_id"), table_name="weekly_journeys")
    op.drop_index(op.f("ix_weekly_journeys_status"), table_name="weekly_journeys")
    op.drop_table("weekly_journeys")

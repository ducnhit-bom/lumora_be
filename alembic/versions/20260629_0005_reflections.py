"""reflections

Revision ID: 20260629_0005
Revises: 20260629_0004
Create Date: 2026-06-29
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260629_0005"
down_revision: Optional[str] = "20260629_0004"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "reflections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("journey_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mood", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["journey_id"], ["weekly_journeys.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["focus_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_reflections_session_id"),
    )
    op.create_index(op.f("ix_reflections_journey_id"), "reflections", ["journey_id"], unique=False)
    op.create_index(op.f("ix_reflections_session_id"), "reflections", ["session_id"], unique=False)
    op.create_index(op.f("ix_reflections_user_id"), "reflections", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reflections_user_id"), table_name="reflections")
    op.drop_index(op.f("ix_reflections_session_id"), table_name="reflections")
    op.drop_index(op.f("ix_reflections_journey_id"), table_name="reflections")
    op.drop_table("reflections")

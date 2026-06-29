"""user settings

Revision ID: 20260629_0006
Revises: 20260629_0005
Create Date: 2026-06-29
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260629_0006"
down_revision: Optional[str] = "20260629_0005"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("auto_open_reflection", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("preferred_focus_time", sa.String(length=5), nullable=False, server_default="09:00"),
        sa.Column("max_sessions_per_day", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="Asia/Ho_Chi_Minh"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_settings")

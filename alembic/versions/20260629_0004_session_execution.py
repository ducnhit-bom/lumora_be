"""session execution timestamps

Revision ID: 20260629_0004
Revises: 20260628_0003
Create Date: 2026-06-29
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260629_0004"
down_revision: Optional[str] = "20260628_0003"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.add_column("focus_sessions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("focus_sessions", sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("focus_sessions", "skipped_at")
    op.drop_column("focus_sessions", "completed_at")

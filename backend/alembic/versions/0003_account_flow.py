"""account flow support: csrf, rate limits, workspace initialization

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("workspace_initialized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "rate_limits",
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("scope", "subject_hash", "window_start"),
        sa.CheckConstraint("count >= 0", name="ck_rate_limits_count"),
    )
    op.create_index("ix_rate_limits_window_start", "rate_limits", ["window_start"])


def downgrade() -> None:
    raise RuntimeError(
        "0003 is forward-only. Restore from a pre-0003 backup instead."
    )

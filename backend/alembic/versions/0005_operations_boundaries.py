"""operations boundaries: quotas, reservations, admin audit and deletion

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "deletion_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_storage_quota",
        "users",
        "storage_quota_bytes IS NULL OR storage_quota_bytes >= 0",
    )
    op.create_check_constraint(
        "ck_users_deletion_schedule",
        "users",
        "(deletion_requested_at IS NULL AND purge_after IS NULL) OR "
        "(deletion_requested_at IS NOT NULL AND purge_after IS NOT NULL "
        "AND purge_after >= deletion_requested_at)",
    )

    op.execute(
        sa.text(
            "INSERT INTO site_settings (setting_key, setting_value) "
            "VALUES ('registration_enabled', 'true') "
            "ON CONFLICT (setting_key) DO NOTHING"
        )
    )

    op.create_table(
        "storage_reservations",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "purpose",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'upload'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "size_bytes > 0", name="ck_storage_reservations_size"
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_storage_reservations_expiry",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_storage_reservations_user_expiry",
        "storage_reservations",
        ["user_id", "expires_at"],
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True),
        sa.Column("target_document_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["admin_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_created",
        "admin_audit_logs",
        ["created_at"],
    )
    op.create_index(
        "ix_admin_audit_admin_created",
        "admin_audit_logs",
        ["admin_user_id", "created_at"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "0005 is forward-only. Restore from a pre-0005 backup instead."
    )

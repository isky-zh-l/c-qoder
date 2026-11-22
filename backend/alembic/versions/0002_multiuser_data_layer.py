"""multi-user data layer and ownership

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20

This migration upgrades the empty M0 database schema to the multi-user data
layer. It refuses to run if legacy content tables contain rows. Legacy tables
are dropped only after the empty-content guard passes; the database itself is
never dropped.

Forward-only: restore the pre-0002 backup for rollback.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "0002 targets PostgreSQL. The legacy SQLite database stays at 0001."
        )

    legacy_tables = ("documents", "chapters", "blocks", "assets", "profile")
    for table in legacy_tables:
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
        if count:
            raise RuntimeError(
                f"Legacy table {table} contains {count} rows. "
                "Back up the database and define an ownership mapping before "
                "running this migration. Migration aborted without dropping data."
            )

    # Empty M0 schema: remove legacy tables through the migration, not by
    # dropping the database.
    op.drop_table("blocks")
    op.drop_table("profile")
    op.drop_table("documents")
    op.drop_table("chapters")
    op.drop_table("assets")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "site_settings",
        sa.Column("setting_key", sa.String(80), primary_key=True),
        sa.Column("setting_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('email_verify', 'password_reset')",
            name="ck_auth_tokens_purpose",
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_tokens_user_purpose",
        "auth_tokens",
        ["user_id", "purpose", "expires_at"],
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_name", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="ck_assets_size"),
        sa.UniqueConstraint("storage_name", name="uq_assets_storage_name"),
    )
    op.create_index("ix_assets_owner", "assets", ["owner_user_id", "created_at"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("bio", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("avatar_asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name="ck_chapters_sort_order"),
    )
    op.create_index("ix_chapters_owner_sort", "chapters", ["owner_user_id", "sort_order"])

    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("title_key", sa.String(255), nullable=False),
        sa.Column("summary", sa.String(120), server_default=sa.text("''"), nullable=False),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("visibility", sa.String(8), server_default=sa.text("'private'"), nullable=False),
        sa.Column("share_token", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("library_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("chapter_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('note', 'source')", name="ck_documents_kind"),
        sa.CheckConstraint(
            "(kind = 'note' AND language IS NULL) OR (kind = 'source' AND language IN ('c', 'h'))",
            name="ck_documents_language",
        ),
        sa.CheckConstraint("visibility IN ('private', 'public')", name="ck_documents_visibility"),
        sa.CheckConstraint(
            "(visibility = 'private' AND share_token IS NULL) OR (visibility = 'public' AND share_token IS NOT NULL)",
            name="ck_documents_share_state",
        ),
        sa.CheckConstraint("version >= 1", name="ck_documents_version"),
        sa.CheckConstraint("library_order >= 0", name="ck_documents_library_order"),
        sa.CheckConstraint("chapter_order >= 0", name="ck_documents_chapter_order"),
        sa.UniqueConstraint("share_token", name="uq_documents_share_token"),
    )
    op.create_index("ix_documents_owner_library", "documents", ["owner_user_id", "library_order"])
    op.create_index("ix_documents_chapter_order", "documents", ["chapter_id", "chapter_order"])
    op.create_index("ix_documents_owner_updated", "documents", ["owner_user_id", "updated_at"])
    op.create_index("ix_documents_deleted_at", "documents", ["owner_user_id", "deleted_at"])
    op.create_index(
        "uq_documents_owner_title_active",
        "documents",
        ["owner_user_id", "title_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "document_favorites",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("favorite_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "document_id"),
        sa.CheckConstraint("favorite_order >= 0", name="ck_favorites_order"),
    )
    op.create_index("ix_favorites_user_order", "document_favorites", ["user_id", "favorite_order"])

    op.create_table(
        "blocks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_type", sa.String(16), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "block_type IN ('rich_text', 'code', 'remark', 'result', 'image', 'formula')",
            name="ck_blocks_type",
        ),
        sa.CheckConstraint(
            "(block_type = 'image' AND asset_id IS NOT NULL) OR (block_type <> 'image' AND asset_id IS NULL)",
            name="ck_blocks_image_asset",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_blocks_sort_order"),
    )
    op.create_index("ix_blocks_document_sort", "blocks", ["document_id", "sort_order"])

    op.create_table(
        "recycle_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_chapter_id", sa.BigInteger(), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("document_id", name="uq_recycle_document"),
    )
    op.create_index("ix_recycle_owner_deleted", "recycle_entries", ["owner_user_id", "deleted_at"])

    op.execute(
        sa.text(
            "INSERT INTO site_settings (setting_key, setting_value) "
            "VALUES ('site_name', 'C 语言学习笔记')"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "0002 is forward-only. Restore from the pre-0002 backup instead of "
        "running a destructive downgrade."
    )

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import User
from app.security import hash_password


def test_postgres_alembic_state_and_ownership_columns(db_session):
    version = db_session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()
    assert version == "0005"

    tables = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars()
    )
    expected = {
        "users",
        "user_profiles",
        "site_settings",
        "sessions",
        "auth_tokens",
        "chapters",
        "documents",
        "document_favorites",
        "document_publications",
        "blocks",
        "assets",
        "recycle_entries",
        "rate_limits",
        "storage_reservations",
        "admin_audit_logs",
        "alembic_version",
    }
    assert expected <= tables
    assert "profile" not in tables

    required_owner_columns = {
        "chapters": "owner_user_id",
        "documents": "owner_user_id",
        "assets": "owner_user_id",
        "recycle_entries": "owner_user_id",
        "document_favorites": "user_id",
        "user_profiles": "user_id",
        "rate_limits": "subject_hash",
    }
    for table, column in required_owner_columns.items():
        values = set(
            db_session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :table"
                ),
                {"table": table},
            ).scalars()
        )
        assert column in values, (table, values)

    users_columns = set(
        db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users'"
            )
        ).scalars()
    )
    assert "workspace_initialized_at" in users_columns
    assert "is_admin" in users_columns
    assert "storage_quota_bytes" in users_columns
    assert "deletion_requested_at" in users_columns
    assert "purge_after" in users_columns
    session_columns = set(
        db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'sessions'"
            )
        ).scalars()
    )
    assert "csrf_token_hash" in session_columns

    index_names = set(
        db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public'"
            )
        ).scalars()
    )
    assert "uq_documents_owner_title_active" in index_names
    assert "ix_documents_owner_library" in index_names
    assert "ix_favorites_user_order" in index_names
    assert "ix_storage_reservations_user_expiry" in index_names
    assert "ix_admin_audit_created" in index_names

    assert (
        db_session.execute(
            text(
                "SELECT setting_value FROM site_settings "
                "WHERE setting_key = 'site_name'"
            )
        ).scalar_one()
        == "C 语言学习笔记"
    )
    assert (
        db_session.execute(
            text(
                "SELECT setting_value FROM site_settings "
                "WHERE setting_key = 'registration_enabled'"
            )
        ).scalar_one()
        == "true"
    )


def test_user_email_is_unique(alice, db_session):
    duplicate = User(
        email=alice.email,
        password_hash=hash_password("another-password-123"),
    )
    db_session.add(duplicate)
    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("duplicate email should violate the database constraint")

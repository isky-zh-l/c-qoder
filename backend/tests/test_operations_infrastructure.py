import logging
import os
from datetime import timedelta

from app.config import get_settings
from app.logging_utils import RedactionFilter, redact_sensitive
from app.main import app
from app.models import Asset
from app.security import utcnow
from app.services.assets import asset_path
from app.services.maintenance import (
    delete_orphan_files,
    scan_orphan_files,
)
from helpers import API

settings = get_settings()


def test_authenticated_api_responses_are_not_cacheable(alice_client):
    response = alice_client.get(f"{API}/me")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["pragma"] == "no-cache"


def test_log_redaction_for_email_session_and_share_tokens():
    message = (
        "GET /c/verify-email?token=email-secret&x=1 "
        "/c/p/share-secret "
        "/c/api/v1/public/documents/public-secret/assets/1 "
        "c_session=session-secret; password=password-secret"
    )
    redacted = redact_sensitive(message)
    for secret in (
        "email-secret",
        "share-secret",
        "public-secret",
        "session-secret",
        "password-secret",
    ):
        assert secret not in redacted
    assert "[REDACTED]" in redacted

    record = logging.LogRecord(
        "c_notes",
        logging.INFO,
        __file__,
        1,
        message,
        (),
        None,
    )
    assert RedactionFilter().filter(record) is True
    assert "email-secret" not in record.getMessage()
    assert "session-secret" not in record.getMessage()

    access = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "127.0.0.1:1",
            "GET",
            "/c/verify-email?token=access-secret",
            "1.1",
            200,
        ),
        None,
    )
    assert RedactionFilter().filter(access) is True
    assert access.args[2] == "/c/verify-email?token=[REDACTED]"
    assert access.getMessage().endswith('200')


def test_health_reports_unwritable_upload_directory(
    anon_client,
    monkeypatch,
    tmp_path,
):
    blocker = tmp_path / "uploads-is-a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(settings, "uploads_dir", str(blocker))
    response = anon_client.get(f"{API}/health")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["uploads"] == "error"
    assert payload["database"] == "ok"


def test_request_rate_limit_is_configurable(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_request_per_minute", 1)
    first = anon_client.get(f"{API}/public/site")
    second = anon_client.get(f"{API}/public/site")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    assert "retry_after" in second.json()["error"]["details"]


def test_orphan_cleanup_only_deletes_unreferenced_files(
    alice, db_session
):
    owner_dir = settings.uploads_path / str(alice.id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    orphan = owner_dir / "orphan.png"
    orphan.write_bytes(b"orphan")
    old = (utcnow() - timedelta(days=3)).timestamp()
    os.utime(orphan, (old, old))

    missing = Asset(
        owner_user_id=alice.id,
        storage_name="missing.png",
        original_name="missing.png",
        mime_type="image/png",
        size_bytes=3,
    )
    db_session.add(missing)
    db_session.commit()

    report = scan_orphan_files(db_session, grace_hours=1)
    assert orphan in report.files
    assert asset_path(alice.id, "missing.png") in report.missing

    removed = delete_orphan_files(report)
    assert removed == 1
    assert not orphan.exists()
    db_session.expire_all()
    assert db_session.get(Asset, missing.id) is not None

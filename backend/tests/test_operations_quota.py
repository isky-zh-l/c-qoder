import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import StorageReservation
from app.services.storage import release_reservation, reserve_storage
from helpers import (
    API,
    PNG_BYTES,
    code_block,
    create_document,
    error_code,
    image_block,
    rich_text_block,
    upload_asset,
    version_headers,
)

settings = get_settings()


def _text_block(markdown: str) -> dict:
    return {
        "block_type": "rich_text",
        "content": {"module": "paragraph", "markdown": markdown},
        "asset_id": None,
    }


def test_usage_breakdown_quota_rejection_and_temp_cleanup(
    alice,
    alice_client,
    db_session,
):
    note = create_document(alice_client, "Usage Note")
    saved = alice_client.put(
        f"{API}/documents/{note['id']}/blocks",
        headers=version_headers(note["version"]),
        json={"blocks": [rich_text_block("usage note")]},
    )
    assert saved.status_code == 200, saved.text

    source = create_document(
        alice_client,
        "Usage Source",
        kind="source",
        language="c",
    )
    saved_source = alice_client.put(
        f"{API}/documents/{source['id']}/blocks",
        headers=version_headers(source["version"]),
        json={"blocks": [code_block("int main(void) { return 0; }")]},
    )
    assert saved_source.status_code == 200, saved_source.text

    asset = upload_asset(alice_client, name="usage.png")
    note_version = saved.json()["version"]
    saved_image = alice_client.put(
        f"{API}/documents/{note['id']}/blocks",
        headers=version_headers(note_version),
        json={
            "blocks": [
                rich_text_block("usage note"),
                image_block(asset["id"], "usage"),
            ]
        },
    )
    assert saved_image.status_code == 200, saved_image.text

    assert alice_client.delete(f"{API}/documents/{source['id']}").status_code == 204

    usage_response = alice_client.get(f"{API}/me/usage")
    assert usage_response.status_code == 200, usage_response.text
    usage = usage_response.json()
    assert usage["source_bytes"] == 0
    assert usage["note_bytes"] > 0
    assert usage["image_bytes"] >= len(PNG_BYTES)
    assert usage["recycle_bytes"] > 0
    assert usage["document_count"] == 1
    assert usage["recycle_count"] == 1
    assert usage["used_bytes"] == (
        usage["note_bytes"]
        + usage["image_bytes"]
        + usage["recycle_bytes"]
    )

    alice.storage_quota_bytes = usage["used_bytes"]
    db_session.commit()

    current = alice_client.get(f"{API}/documents/{note['id']}").json()
    too_large = alice_client.put(
        f"{API}/documents/{note['id']}/blocks",
        headers=version_headers(current["version"]),
        json={
            "blocks": [
                rich_text_block("usage note"),
                image_block(asset["id"], "usage"),
                _text_block("x" * 4096),
            ]
        },
    )
    assert too_large.status_code == 413, too_large.text
    assert error_code(too_large) == "storage_quota_exceeded"
    unchanged = alice_client.get(f"{API}/documents/{note['id']}").json()
    assert unchanged["version"] == current["version"]

    temp_files_before = set(settings.storage_tmp_path.glob("*"))
    upload = alice_client.post(
        f"{API}/assets",
        files={"file": ("blocked.png", PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 413, upload.text
    assert error_code(upload) == "storage_quota_exceeded"
    assert set(settings.storage_tmp_path.glob("*")) == temp_files_before
    assets = alice_client.get(f"{API}/workspace").json()["storage"]["asset_count"]
    assert assets == 1


def test_concurrent_reservations_never_overcommit_quota(alice, db_session):
    alice.storage_quota_bytes = 100
    db_session.commit()

    barrier = threading.Barrier(2)

    def worker():
        db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            reservation = reserve_storage(db, alice.id, 75)
            return ("ok", reservation.id)
        except Exception as exc:
            return ("error", getattr(exc, "status_code", None), str(exc))
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: worker(), range(2)))

    successes = [item for item in results if item[0] == "ok"]
    errors = [item for item in results if item[0] == "error"]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    assert errors[0][1] == 413, results

    db_session.expire_all()
    reserved = db_session.scalar(
        select(func.coalesce(func.sum(StorageReservation.size_bytes), 0))
    )
    assert reserved == 75
    release_reservation(db_session, successes[0][1])
    assert (
        db_session.scalar(select(func.count()).select_from(StorageReservation))
        == 0
    )


def test_image_is_really_decoded_and_stored_with_safe_name(alice_client):
    uploaded = alice_client.post(
        f"{API}/assets",
        files={
            "file": (
                "payload.exe",
                PNG_BYTES,
                "application/octet-stream",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    payload = uploaded.json()
    assert payload["mime_type"] == "image/png"
    assert payload["original_name"] == "payload.png"
    assert not payload["original_name"].endswith(".exe")
    assert alice_client.get(
        f"{API}/assets/{payload['id']}/file"
    ).content == PNG_BYTES

    invalid = alice_client.post(
        f"{API}/assets",
        files={"file": ("evil.png", b"#!/bin/sh\necho hacked", "image/png")},
    )
    assert invalid.status_code == 415, invalid.text
    assert error_code(invalid) == "unsupported_media_type"
    assert not list(settings.storage_tmp_path.glob("*.upload"))


def test_image_config_limits_are_enforced(
    alice_client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "max_image_bytes", 10)
    response = alice_client.post(
        f"{API}/assets",
        files={"file": ("small.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 413, response.text
    assert error_code(response) == "payload_too_large"
    assert not list(settings.storage_tmp_path.glob("*.upload"))

    monkeypatch.setattr(settings, "max_image_bytes", 10 * 1024 * 1024)
    monkeypatch.setattr(settings, "image_max_dimension", 1)
    response = alice_client.post(
        f"{API}/assets",
        files={"file": ("dimension.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 413, response.text
    assert not list(settings.storage_tmp_path.glob("*.upload"))

def test_public_snapshot_counts_in_quota_and_frees_on_unpublish(
    alice,
    alice_client,
    db_session,
):
    document = create_document(alice_client, "Snapshot Quota")
    saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={"blocks": [_text_block("snapshot quota body")]},
    )
    assert saved.status_code == 200, saved.text
    before = alice_client.get(f"{API}/me/usage").json()
    assert before["publication_bytes"] == 0

    alice.storage_quota_bytes = before["used_bytes"]
    db_session.commit()
    rejected = alice_client.put(
        f"{API}/documents/{document['id']}/visibility",
        json={"visibility": "public"},
    )
    assert rejected.status_code == 413, rejected.text
    assert error_code(rejected) == "storage_quota_exceeded"
    unchanged = alice_client.get(
        f"{API}/documents/{document['id']}"
    ).json()
    assert unchanged["visibility"] == "private"
    assert unchanged["published_version"] is None

    alice.storage_quota_bytes = before["used_bytes"] + 100000
    db_session.commit()
    published = alice_client.put(
        f"{API}/documents/{document['id']}/visibility",
        json={"visibility": "public"},
    )
    assert published.status_code == 200, published.text
    after_publish = alice_client.get(f"{API}/me/usage").json()
    assert after_publish["publication_bytes"] > 0
    assert after_publish["used_bytes"] == (
        before["used_bytes"] + after_publish["publication_bytes"]
    )

    unpublished = alice_client.put(
        f"{API}/documents/{document['id']}/visibility",
        json={"visibility": "private"},
    )
    assert unpublished.status_code == 200
    after_unpublish = alice_client.get(f"{API}/me/usage").json()
    assert after_unpublish["publication_bytes"] == 0
    assert after_unpublish["used_bytes"] == before["used_bytes"]


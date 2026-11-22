import io
import json
import zipfile

from app.config import get_settings
from app.models import User
from app.services.assets import asset_path
from app.services.exporting import _sanitize_export_value
from app.services.maintenance import purge_due_accounts
from app.security import utcnow
from helpers import (
    API,
    PNG_BYTES,
    PASSWORD_ALICE,
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


def _make_exportable_document(alice_client):
    document = create_document(alice_client, "导出笔记")
    asset = upload_asset(alice_client, name="export.png")
    saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={
            "blocks": [
                _text_block("导出正文"),
                image_block(asset["id"], "export"),
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    return saved.json(), asset


def test_export_zip_contains_data_and_assets_without_secrets(alice_client):
    document, asset = _make_exportable_document(alice_client)
    published = alice_client.put(
        f"{API}/documents/{document['id']}/visibility",
        json={"visibility": "public"},
    )
    assert published.status_code == 200, published.text
    share_token = published.json()["share_token"]
    sanitized = _sanitize_export_value(
        f"/c/api/v1/public/documents/{share_token}/assets/{asset['id']}"
    )
    assert share_token not in sanitized
    assert "[REDACTED]" in sanitized

    response = alice_client.get(f"{API}/me/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert "c-notes-export" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "data.json" in names
        assert any(name.startswith("assets/") for name in names)
        data = json.loads(archive.read("data.json"))
        asset_file = next(
            name for name in names if name.startswith("assets/")
        )
        assert archive.read(asset_file) == PNG_BYTES

    assert data["format"] == "c-notes-export-v1"
    assert data["user"]["email"] == "alice@example.com"
    assert any(item["id"] == document["id"] for item in data["documents"])
    assert any(item["id"] == asset["id"] for item in data["assets"])
    assert share_token not in json.dumps(data, ensure_ascii=False)
    assert data["documents"][0]["publication"] is not None
    raw = json.dumps(data, ensure_ascii=False)
    for secret in (
        "password_hash",
        "share_token",
        "csrf_token",
        "session_token",
        "token_hash",
    ):
        assert secret not in raw


def test_account_deletion_revokes_public_content_and_purges_after_retention(
    alice,
    alice_client,
    bob_client,
    db_session,
):
    document, asset = _make_exportable_document(alice_client)
    published = alice_client.put(
        f"{API}/documents/{document['id']}/visibility",
        json={"visibility": "public"},
    )
    assert published.status_code == 200, published.text
    token = published.json()["share_token"]
    assert bob_client.get(
        f"{API}/public/documents/{token}"
    ).status_code == 200

    wrong_confirmation = alice_client.post(
        f"{API}/me/delete",
        json={
            "current_password": PASSWORD_ALICE,
            "confirmation": "删除",
        },
    )
    assert wrong_confirmation.status_code == 422

    wrong_password = alice_client.post(
        f"{API}/me/delete",
        json={
            "current_password": "wrong-password-123",
            "confirmation": "注销账号",
        },
    )
    assert wrong_password.status_code == 400
    assert error_code(wrong_password) == "invalid_credentials"

    deleted = alice_client.post(
        f"{API}/me/delete",
        json={
            "current_password": PASSWORD_ALICE,
            "confirmation": "注销账号",
        },
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["retention_days"] == settings.account_deletion_retention_days
    assert alice_client.get(f"{API}/me").status_code == 401
    assert bob_client.get(f"{API}/public/documents/{token}").status_code == 404

    login = alice_client.post(
        f"{API}/auth/login",
        json={"email": alice.email, "password": PASSWORD_ALICE},
    )
    assert login.status_code == 403
    assert error_code(login) == "account_disabled"

    file_path = asset_path(alice.id, _asset_storage_name(db_session, asset["id"]))
    assert file_path.is_file()

    db_session.expire_all()
    user = db_session.get(User, alice.id)
    assert user is not None
    user.purge_after = utcnow()
    db_session.commit()

    assert purge_due_accounts(db_session) == 1
    db_session.expire_all()
    assert db_session.get(User, alice.id) is None
    assert not file_path.exists()


def _asset_storage_name(db_session, asset_id: int) -> str:
    from app.models import Asset

    asset = db_session.get(Asset, asset_id)
    assert asset is not None
    return asset.storage_name

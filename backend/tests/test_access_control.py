import pytest
from sqlalchemy import func, select

from app.models import UserProfile
from helpers import (
    API,
    PASSWORD_ALICE,
    PASSWORD_EXTRA,
    create_chapter,
    create_document,
    error_code,
    image_block,
    rich_text_block,
    upload_asset,
    version_headers,
)


def test_anonymous_only_public_endpoints(anon_client):
    root = anon_client.get("/", follow_redirects=False)
    assert root.status_code == 308
    assert root.headers["location"] == "/c/"
    assert anon_client.get(f"{API}/health").status_code == 200
    site = anon_client.get(f"{API}/public/site")
    assert site.status_code == 200
    assert site.json() == {
        "site_title": "C 语言学习笔记",
        "registration_enabled": True,
    }
    assert anon_client.get(f"{API}/auth/session").json()["authenticated"] is False

    protected = [
        f"{API}/me",
        f"{API}/chapters",
        f"{API}/documents",
        f"{API}/documents/1",
        f"{API}/favorites/count",
        f"{API}/recycle",
        f"{API}/assets/1/file",
        f"{API}/assets/1/download",
    ]
    for path in protected:
        response = anon_client.get(path)
        assert response.status_code == 401, (path, response.text)
        assert error_code(response) == "unauthenticated"

    assert anon_client.post(f"{API}/chapters", json={"name": "x"}).status_code == 401
    assert (
        anon_client.put(
            f"{API}/documents/1/blocks", json={"blocks": []}
        ).status_code
        == 401
    )
    assert (
        anon_client.put(
            f"{API}/orders/library", json={"document_ids": []}
        ).status_code
        == 401
    )

    # The old anonymous directory endpoints are retired.
    assert anon_client.get(f"{API}/site").status_code == 404


def test_login_gates_session_and_profile(
    alice,
    alice_client,
    anon_client,
    make_test_user,
    db_session,
):
    unverified = make_test_user(
        "unverified@example.com",
        PASSWORD_EXTRA,
        "Unverified",
        verified=False,
    )
    disabled = make_test_user(
        "disabled@example.com",
        PASSWORD_EXTRA,
        "Disabled",
        enabled=False,
    )

    response = anon_client.post(
        f"{API}/auth/login",
        json={"email": unverified.email, "password": PASSWORD_EXTRA},
    )
    assert response.status_code == 403
    assert error_code(response) == "email_not_verified"

    response = anon_client.post(
        f"{API}/auth/login",
        json={"email": disabled.email, "password": PASSWORD_EXTRA},
    )
    assert response.status_code == 403
    assert error_code(response) == "account_disabled"

    response = anon_client.post(
        f"{API}/auth/login",
        json={"email": alice.email, "password": "wrong-password-123"},
    )
    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"

    session = alice_client.get(f"{API}/auth/session").json()
    assert session["authenticated"] is True
    assert session["user"]["id"] == alice.id

    me = alice_client.get(f"{API}/me")
    assert me.status_code == 200
    assert me.json()["email"] == alice.email

    profile = db_session.scalar(
        select(func.count())
        .select_from(UserProfile)
        .where(UserProfile.user_id == alice.id)
    )
    assert profile == 1

    updated = alice_client.patch(
        f"{API}/me/profile",
        json={"display_name": "Alice Updated", "bio": "hello"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Alice Updated"
    assert updated.json()["bio"] == "hello"

    with pytest.raises(ValueError):
        make_test_user("ALICE@EXAMPLE.COM", PASSWORD_EXTRA, "Duplicate")

    logout = alice_client.post(f"{API}/auth/logout")
    assert logout.status_code == 204
    assert alice_client.get(f"{API}/auth/session").json()["authenticated"] is False


def test_disabled_account_invalidates_existing_session(
    alice, alice_client, db_session
):
    alice.is_enabled = False
    db_session.commit()
    response = alice_client.get(f"{API}/chapters")
    assert response.status_code == 401
    assert error_code(response) == "unauthenticated"


def test_cross_user_access_is_denied_everywhere(
    alice,
    bob,
    alice_client,
    bob_client,
):
    chapter_a = create_chapter(alice_client, "Alice Chapter")
    document_a = create_document(
        alice_client, "Alice Document", chapter_id=chapter_a["id"]
    )
    asset_a = upload_asset(alice_client)
    alice_client.put(f"{API}/documents/{document_a['id']}/favorite")

    assert bob_client.get(f"{API}/documents").json() == []
    assert bob_client.get(f"{API}/documents/{document_a['id']}").status_code == 404

    patch = bob_client.patch(
        f"{API}/documents/{document_a['id']}",
        headers=version_headers(1),
        json={"title": "Stolen"},
    )
    assert patch.status_code == 404

    blocks = bob_client.put(
        f"{API}/documents/{document_a['id']}/blocks",
        headers=version_headers(1),
        json={"blocks": [rich_text_block("stolen")]},
    )
    assert blocks.status_code == 404

    favorite = bob_client.put(f"{API}/documents/{document_a['id']}/favorite")
    assert favorite.status_code == 404

    chapter_scope = bob_client.get(
        f"{API}/documents",
        params={"scope": "chapter", "chapter_id": chapter_a["id"]},
    )
    assert chapter_scope.status_code == 404

    chapter_assoc = bob_client.post(
        f"{API}/documents",
        json={
            "kind": "note",
            "title": "Bob Bad Chapter",
            "chapter_id": chapter_a["id"],
        },
    )
    assert chapter_assoc.status_code == 404

    asset_file = bob_client.get(f"{API}/assets/{asset_a['id']}/file")
    asset_download = bob_client.get(f"{API}/assets/{asset_a['id']}/download")
    assert asset_file.status_code == 404
    assert asset_download.status_code == 404

    avatar = bob_client.patch(
        f"{API}/me/profile",
        json={"avatar_asset_id": asset_a["id"]},
    )
    assert avatar.status_code == 404

    bob_doc = create_document(bob_client, "Bob Document")
    bad_image = bob_client.put(
        f"{API}/documents/{bob_doc['id']}/blocks",
        headers=version_headers(bob_doc["version"]),
        json={"blocks": [image_block(asset_a["id"])]},
    )
    assert bad_image.status_code == 404
    bob_after = bob_client.get(f"{API}/documents/{bob_doc['id']}").json()
    assert bob_after["version"] == 1
    assert bob_after["blocks"] == []

    bob_chapter = create_chapter(bob_client, "Bob Chapter")
    bob_chapter_doc = create_document(
        bob_client, "Bob Chapter Doc", chapter_id=bob_chapter["id"]
    )

    cross_order = bob_client.put(
        f"{API}/orders/library",
        json={"document_ids": [document_a["id"]]},
    )
    assert cross_order.status_code == 409
    assert error_code(cross_order) == "order_conflict"
    assert [d["id"] for d in bob_client.get(f"{API}/documents").json()] == [
        bob_doc["id"],
        bob_chapter_doc["id"],
    ]

    cross_chapter_order = bob_client.put(
        f"{API}/orders/chapters/{chapter_a['id']}",
        json={"document_ids": []},
    )
    assert cross_chapter_order.status_code == 404

    mixed_chapter_order = bob_client.put(
        f"{API}/orders/chapters/{bob_chapter['id']}",
        json={"document_ids": [document_a["id"], bob_chapter_doc["id"]]},
    )
    assert mixed_chapter_order.status_code == 409

    cross_favorite_order = bob_client.put(
        f"{API}/orders/favorites",
        json={"document_ids": [document_a["id"]]},
    )
    assert cross_favorite_order.status_code == 409

    alice_client.delete(f"{API}/documents/{document_a['id']}")
    assert bob_client.get(f"{API}/recycle").json() == []
    recycle_id = alice_client.get(f"{API}/recycle").json()[0]["id"]
    denied_restore = bob_client.post(
        f"{API}/recycle/{recycle_id}/restore", json={}
    )
    assert denied_restore.status_code == 404

    extra_owner = alice_client.post(
        f"{API}/documents",
        json={
            "kind": "note",
            "title": "Owner Injection",
            "owner_user_id": bob.id,
        },
    )
    assert extra_owner.status_code == 422


def test_same_user_name_conflicts_and_stable_ids(alice_client, bob_client):
    first = create_document(alice_client, "Same Name")
    duplicate = alice_client.post(
        f"{API}/documents",
        json={"kind": "note", "title": "same name"},
    )
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "document_name_conflict"

    duplicate_spaced = alice_client.post(
        f"{API}/documents",
        json={"kind": "note", "title": "  Same Name  "},
    )
    assert duplicate_spaced.status_code == 409

    bob_doc = create_document(bob_client, "Same Name")
    assert bob_doc["id"] != first["id"]

    renamed = alice_client.patch(
        f"{API}/documents/{first['id']}",
        headers=version_headers(first["version"]),
        json={"title": "Renamed"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["id"] == first["id"]
    assert renamed.json()["title"] == "Renamed"

    other = create_document(alice_client, "Other")
    conflict = alice_client.patch(
        f"{API}/documents/{other['id']}",
        headers=version_headers(other["version"]),
        json={"title": "renamed"},
    )
    assert conflict.status_code == 409
    assert error_code(conflict) == "document_name_conflict"

    alice_client.delete(f"{API}/documents/{first['id']}")
    replacement = create_document(alice_client, "Renamed")
    assert replacement["id"] != first["id"]

    recycle_entry = alice_client.get(f"{API}/recycle").json()[0]
    restore_conflict = alice_client.post(
        f"{API}/recycle/{recycle_entry['id']}/restore", json={}
    )
    assert restore_conflict.status_code == 409
    assert error_code(restore_conflict) == "document_name_conflict"

    restored = alice_client.post(
        f"{API}/recycle/{recycle_entry['id']}/restore",
        json={"title": "Renamed Restored"},
    )
    assert restored.status_code == 200
    assert restored.json()["id"] == first["id"]
    assert restored.json()["title"] == "Renamed Restored"


def test_chapter_delete_moves_documents_to_uncategorized(
    alice_client, bob_client
):
    chapter = create_chapter(alice_client, "Temporary")
    bob_chapter = create_chapter(bob_client, "Bob Temporary")
    document = create_document(
        alice_client, "Chapter Document", chapter_id=chapter["id"]
    )

    assert alice_client.delete(f"{API}/chapters/{chapter['id']}").status_code == 204
    detail = alice_client.get(f"{API}/documents/{document['id']}")
    assert detail.status_code == 200
    assert detail.json()["chapter_id"] is None
    assert alice_client.get(f"{API}/chapters").json() == []
    assert bob_client.get(f"{API}/chapters").json()[0]["id"] == bob_chapter["id"]

from helpers import (
    API,
    PASSWORD_ADMIN,
    PASSWORD_BOB,
    create_document,
    error_code,
    register_user,
    rich_text_block,
    version_headers,
)


def _text_block(markdown: str) -> dict:
    return {
        "block_type": "rich_text",
        "content": {"module": "paragraph", "markdown": markdown},
        "asset_id": None,
    }


def test_admin_permissions_registration_quota_and_public_takedown(
    admin,
    admin_client,
    alice_client,
    bob,
    bob_client,
    anon_client,
    login_as,
    db_session,
):
    assert alice_client.get(f"{API}/admin/settings").status_code == 403

    assert alice_client.get(f"{API}/public/site").json()[
        "registration_enabled"
    ] is True
    disabled = admin_client.put(
        f"{API}/admin/settings/registration",
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert anon_client.get(f"{API}/public/site").json()[
        "registration_enabled"
    ] is False
    blocked = register_user(
        anon_client,
        "new-user@example.com",
        "new-user-password-123",
        "New User",
    )
    assert blocked.status_code == 403
    assert error_code(blocked) == "registration_disabled"

    enabled = admin_client.put(
        f"{API}/admin/settings/registration",
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert anon_client.get(f"{API}/public/site").json()[
        "registration_enabled"
    ] is True

    listed = admin_client.get(f"{API}/admin/users")
    assert listed.status_code == 200, listed.text
    users = listed.json()["users"]
    assert listed.json()["total"] >= 3
    bob_row = next(item for item in users if item["id"] == bob.id)
    assert bob_row["is_admin"] is False
    assert bob_row["effective_quota_bytes"] > 0

    quota = admin_client.put(
        f"{API}/admin/users/{bob.id}/quota",
        json={"quota_bytes": 123456},
    )
    assert quota.status_code == 200, quota.text
    assert quota.json()["storage_quota_bytes"] == 123456
    assert quota.json()["effective_quota_bytes"] == 123456

    bob_doc = create_document(bob_client, "Bob Public")
    saved = bob_client.put(
        f"{API}/documents/{bob_doc['id']}/blocks",
        headers=version_headers(bob_doc["version"]),
        json={"blocks": [_text_block("bob public body")]},
    )
    assert saved.status_code == 200, saved.text
    published = bob_client.put(
        f"{API}/documents/{bob_doc['id']}/visibility",
        json={"visibility": "public"},
    )
    assert published.status_code == 200, published.text
    token = published.json()["share_token"]
    assert anon_client.get(f"{API}/public/documents/{token}").status_code == 200

    suspended = admin_client.put(
        f"{API}/admin/users/{bob.id}/status",
        json={"enabled": False},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["is_enabled"] is False
    assert anon_client.get(f"{API}/public/documents/{token}").status_code == 404
    assert bob_client.get(f"{API}/me").status_code == 401
    bob_login = bob_client.post(
        f"{API}/auth/login",
        json={"email": bob.email, "password": PASSWORD_BOB},
    )
    assert bob_login.status_code == 403
    assert error_code(bob_login) == "account_disabled"

    restored = admin_client.put(
        f"{API}/admin/users/{bob.id}/status",
        json={"enabled": True},
    )
    assert restored.status_code == 200, restored.text
    bob_again = login_as(bob.email, PASSWORD_BOB)
    bob_document = bob_again.get(f"{API}/documents/{bob_doc['id']}").json()
    assert bob_document["visibility"] == "private"
    assert anon_client.get(f"{API}/public/documents/{token}").status_code == 404

    admin_me = admin_client.get(f"{API}/me").json()
    self_suspend = admin_client.put(
        f"{API}/admin/users/{admin_me['id']}/status",
        json={"enabled": False},
    )
    assert self_suspend.status_code == 409
    assert error_code(self_suspend) == "self_action_not_allowed"

    alice_doc = create_document(alice_client, "Alice Public Moderation")
    alice_saved = alice_client.put(
        f"{API}/documents/{alice_doc['id']}/blocks",
        headers=version_headers(alice_doc["version"]),
        json={"blocks": [_text_block("alice public body")]},
    )
    assert alice_saved.status_code == 200, alice_saved.text
    alice_published = alice_client.put(
        f"{API}/documents/{alice_doc['id']}/visibility",
        json={"visibility": "public"},
    )
    assert alice_published.status_code == 200
    alice_token = alice_published.json()["share_token"]
    public_list = admin_client.get(f"{API}/admin/publications")
    assert public_list.status_code == 200, public_list.text
    public_row = next(
        item
        for item in public_list.json()["documents"]
        if item["document_id"] == alice_doc["id"]
    )
    assert public_row["share_url"]
    assert public_row["owner_email"] == "alice@example.com"
    removed = admin_client.delete(
        f"{API}/admin/publications/{alice_doc['id']}"
    )
    assert removed.status_code == 204
    assert anon_client.get(f"{API}/public/documents/{alice_token}").status_code == 404
    alice_after = alice_client.get(f"{API}/documents/{alice_doc['id']}").json()
    assert alice_after["visibility"] == "private"

    audit = admin_client.get(f"{API}/admin/audit")
    assert audit.status_code == 200, audit.text
    actions = {entry["action"] for entry in audit.json()["entries"]}
    assert {
        "registration.set",
        "user.quota",
        "user.status",
        "publication.unpublish",
    } <= actions


def test_last_admin_cannot_initiate_account_deletion(admin_client):
    response = admin_client.post(
        f"{API}/me/delete",
        json={
            "current_password": PASSWORD_ADMIN,
            "confirmation": "注销账号",
        },
    )
    assert response.status_code == 409
    assert error_code(response) == "last_admin"

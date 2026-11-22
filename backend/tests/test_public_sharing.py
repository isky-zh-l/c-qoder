from datetime import timedelta

from sqlalchemy import update

from app.config import get_settings
from app.models import Document, RecycleEntry
from app.security import utcnow
from helpers import (
    PNG_BYTES,
    API,
    PASSWORD_ALICE,
    create_chapter,
    create_document,
    error_code,
    get_document,
    image_block,
    upload_asset,
    version_headers,
)


def text_module(markdown: str) -> dict:
    return {
        "block_type": "rich_text",
        "content": {"module": "paragraph", "markdown": markdown},
        "asset_id": None,
    }


def publish(client, document_id: int):
    return client.put(
        f"{API}/documents/{document_id}/visibility",
        json={"visibility": "public"},
    )


def unpublish(client, document_id: int):
    return client.put(
        f"{API}/documents/{document_id}/visibility",
        json={"visibility": "private"},
    )


def public_document(client, token: str):
    return client.get(f"{API}/public/documents/{token}")


def public_asset(client, token: str, asset_id: int):
    return client.get(
        f"{API}/public/documents/{token}/assets/{asset_id}"
    )


def test_publish_snapshot_public_read_unpublish_and_rotation(
    alice, alice_client, bob_client, anon_client
):
    chapter = create_chapter(alice_client, "公开章节")
    document = create_document(
        alice_client, "公开文章", chapter_id=chapter["id"]
    )
    saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={"blocks": [text_module("发布时的正文")]},
    )
    assert saved.status_code == 200

    published = publish(alice_client, document["id"])
    assert published.status_code == 200, published.text
    publication = published.json()
    assert publication["visibility"] == "public"
    assert publication["share_token"]
    assert publication["share_url"] == f"/c/p/{publication['share_token']}"
    assert publication["published_version"] == saved.json()["version"]

    owner_detail = get_document(alice_client, document["id"])
    assert owner_detail["share_token"] == publication["share_token"]
    assert owner_detail["share_url"] == publication["share_url"]
    assert owner_detail["published_version"] == saved.json()["version"]

    token = publication["share_token"]
    public = public_document(anon_client, token)
    assert public.status_code == 200, public.text
    public_payload = public.json()
    assert set(public_payload) == {
        "title",
        "kind",
        "language",
        "author",
        "published_at",
        "blocks",
    }
    assert public_payload["title"] == "公开文章"
    assert public_payload["author"] == {"display_name": "Alice"}
    assert public_payload["blocks"][0]["content"]["markdown"] == "发布时的正文"
    assert "no-store" in public.headers["cache-control"]
    assert public.headers["x-robots-tag"].startswith("noindex")
    public_text = public.text
    for private_marker in (
        "alice@example.com",
        "chapter_id",
        "chapter_name",
        "owner_user_id",
        "favorite_count",
        "recycle_count",
        "library_count",
        "is_favorite",
    ):
        assert private_marker not in public_text

    # Bob may read the public link, but cannot manage Alice's document.
    assert public_document(bob_client, token).status_code == 200
    assert bob_client.put(
        f"{API}/documents/{document['id']}/visibility",
        json={"visibility": "private"},
    ).status_code == 404
    assert bob_client.put(
        f"{API}/documents/{document['id']}/favorite"
    ).status_code == 404

    # Editing after publication does not change the current public snapshot.
    edited = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(saved.json()["version"]),
        json={
            "title": "编辑中的新标题",
            "blocks": [text_module("编辑中的新正文")],
        },
    )
    assert edited.status_code == 200
    untouched = public_document(anon_client, token)
    assert untouched.json()["title"] == "公开文章"
    assert untouched.json()["blocks"][0]["content"]["markdown"] == "发布时的正文"

    # Explicitly republish current saved version; the share token stays stable.
    republished = publish(alice_client, document["id"])
    assert republished.status_code == 200
    assert republished.json()["share_token"] == token
    refreshed = public_document(anon_client, token).json()
    assert refreshed["title"] == "编辑中的新标题"
    assert refreshed["blocks"][0]["content"]["markdown"] == "编辑中的新正文"

    revoked = unpublish(alice_client, document["id"])
    assert revoked.status_code == 200
    assert revoked.json()["visibility"] == "private"
    assert revoked.json()["share_token"] is None
    assert revoked.headers["clear-site-data"] == '"cache"'
    old_link = public_document(anon_client, token)
    assert old_link.status_code == 404
    assert error_code(old_link) == "share_not_found"
    assert "no-store" in old_link.headers["cache-control"]
    assert get_document(alice_client, document["id"])["share_token"] is None

    # A new publication gets a new token; the old token never revives.
    second = publish(alice_client, document["id"])
    assert second.status_code == 200
    new_token = second.json()["share_token"]
    assert new_token != token
    assert public_document(anon_client, token).status_code == 404
    assert public_document(anon_client, new_token).status_code == 200

    random_token = "not-a-real-share-token"
    assert public_document(anon_client, random_token).status_code == 404
    assert anon_client.get(f"{API}/public/documents").status_code in {404, 405}


def test_public_assets_are_scoped_to_the_published_snapshot(
    alice_client, bob_client, anon_client
):
    asset_one = upload_asset(alice_client, name="public.png")
    asset_two = upload_asset(alice_client, name="private.png")
    bob_asset = upload_asset(bob_client, name="bob.png")

    public_doc = create_document(alice_client, "公开图片文章")
    saved_public = alice_client.put(
        f"{API}/documents/{public_doc['id']}/blocks",
        headers=version_headers(public_doc["version"]),
        json={"blocks": [image_block(asset_one["id"], "公开图")]},
    )
    assert saved_public.status_code == 200
    private_doc = create_document(alice_client, "私有图片文章")
    saved_private = alice_client.put(
        f"{API}/documents/{private_doc['id']}/blocks",
        headers=version_headers(private_doc["version"]),
        json={"blocks": [image_block(asset_two["id"], "私有图")]},
    )
    assert saved_private.status_code == 200

    token = publish(alice_client, public_doc["id"]).json()["share_token"]
    public_read = public_asset(anon_client, token, asset_one["id"])
    assert public_read.status_code == 200
    assert public_read.content == PNG_BYTES
    assert "no-store" in public_read.headers["cache-control"]
    assert public_read.headers["x-robots-tag"].startswith("noindex")

    assert public_asset(anon_client, token, asset_two["id"]).status_code == 404
    assert public_asset(anon_client, token, bob_asset["id"]).status_code == 404
    assert public_asset(anon_client, "wrong-token", asset_one["id"]).status_code == 404
    assert public_asset(anon_client, token, 999999).status_code == 404

    traversal = anon_client.get(
        f"{API}/public/documents/{token}/assets/..%2F..%2Fsecret"
    )
    assert traversal.status_code in {404, 422}
    assert b"secret" not in traversal.content
    encoded = anon_client.get(
        f"{API}/public/documents/{token}/assets/%2e%2e%5c%2e%2e%5csecret"
    )
    assert encoded.status_code in {404, 422}

    # Markdown inline images are rewritten to the public asset route.
    inline = create_document(alice_client, "内联公开图片")
    inline_saved = alice_client.put(
        f"{API}/documents/{inline['id']}/blocks",
        headers=version_headers(inline["version"]),
        json={
            "blocks": [
                {
                    "block_type": "rich_text",
                    "content": {
                        "module": "paragraph",
                        "markdown": (
                            f'![alt](/c/api/v1/assets/{asset_one["id"]}/file "说明")'
                        ),
                    },
                    "asset_id": None,
                }
            ]
        },
    )
    assert inline_saved.status_code == 200
    inline_token = publish(alice_client, inline["id"]).json()["share_token"]
    inline_public = public_document(anon_client, inline_token).json()
    inline_markdown = inline_public["blocks"][0]["content"]["markdown"]
    assert (
        f"/public/documents/{inline_token}/assets/{asset_one['id']}"
        in inline_markdown
    )
    assert public_asset(anon_client, inline_token, asset_one["id"]).status_code == 200

    # Unpublishing immediately revokes document and asset access.
    assert unpublish(alice_client, public_doc["id"]).status_code == 200
    assert public_document(anon_client, token).status_code == 404
    assert public_asset(anon_client, token, asset_one["id"]).status_code == 404


def test_recycle_revokes_publication_and_public_snapshot_keeps_asset(
    alice_client, anon_client, db_session
):
    asset = upload_asset(alice_client, name="shared-public.png")
    public_doc = create_document(alice_client, "回收撤销公开")
    saved = alice_client.put(
        f"{API}/documents/{public_doc['id']}/blocks",
        headers=version_headers(public_doc["version"]),
        json={"blocks": [image_block(asset["id"], "公开附件")]},
    )
    assert saved.status_code == 200
    token = publish(alice_client, public_doc["id"]).json()["share_token"]
    assert public_asset(anon_client, token, asset["id"]).status_code == 200

    assert alice_client.delete(
        f"{API}/documents/{public_doc['id']}"
    ).status_code == 204
    assert public_document(anon_client, token).status_code == 404
    assert public_asset(anon_client, token, asset["id"]).status_code == 404
    restored = alice_client.post(
        f"{API}/recycle/{alice_client.get(f'{API}/recycle').json()[0]['id']}/restore",
        json={},
    )
    assert restored.status_code == 200
    assert restored.json()["visibility"] == "private"
    assert restored.json()["share_token"] is None
    assert public_document(anon_client, token).status_code == 404

    # A publication snapshot protects an attachment during recycle cleanup
    # even when the current document no longer references it.
    protected = upload_asset(alice_client, name="protected.png")
    published_doc = create_document(alice_client, "快照引用保护")
    first = alice_client.put(
        f"{API}/documents/{published_doc['id']}/blocks",
        headers=version_headers(published_doc["version"]),
        json={"blocks": [image_block(protected["id"], "快照图")]},
    )
    assert first.status_code == 200
    protected_token = publish(
        alice_client, published_doc["id"]
    ).json()["share_token"]
    removed = alice_client.put(
        f"{API}/documents/{published_doc['id']}/blocks",
        headers=version_headers(first.json()["version"]),
        json={"blocks": [text_module("当前正文不再引用图片")]},
    )
    assert removed.status_code == 200

    recycled = create_document(alice_client, "过期引用文档")
    recycled_saved = alice_client.put(
        f"{API}/documents/{recycled['id']}/blocks",
        headers=version_headers(recycled["version"]),
        json={"blocks": [image_block(protected["id"], "旧引用")]},
    )
    assert recycled_saved.status_code == 200
    assert alice_client.delete(
        f"{API}/documents/{recycled['id']}"
    ).status_code == 204
    old = utcnow() - timedelta(
        days=get_settings().recycle_retention_days + 1
    )
    entry = alice_client.get(f"{API}/recycle").json()[0]
    db_session.execute(
        update(RecycleEntry)
        .where(RecycleEntry.id == entry["id"])
        .values(deleted_at=old)
    )
    db_session.execute(
        update(Document)
        .where(Document.id == recycled["id"])
        .values(deleted_at=old)
    )
    db_session.commit()
    assert alice_client.get(f"{API}/workspace").status_code == 200
    assert public_asset(
        anon_client, protected_token, protected["id"]
    ).status_code == 200

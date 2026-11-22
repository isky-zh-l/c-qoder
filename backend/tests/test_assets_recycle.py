from datetime import timedelta

from sqlalchemy import select

from app.models import Asset, Document, RecycleEntry
from app.security import utcnow
from app.services.recycle import purge_expired_recycle
from helpers import (
    API,
    create_chapter,
    create_document,
    get_document,
    image_block,
    PNG_BYTES,
    rich_text_block,
    upload_asset,
    version_headers,
)


def test_asset_file_download_and_avatar_ownership(
    alice, alice_client, bob_client
):
    asset = upload_asset(
        alice_client,
        name="diagram.png",
        data=PNG_BYTES,
    )
    assert asset["original_name"] == "diagram.png"

    file_response = alice_client.get(f"{API}/assets/{asset['id']}/file")
    assert file_response.status_code == 200
    assert file_response.content == PNG_BYTES
    assert file_response.headers["content-type"].startswith("image/png")
    assert file_response.headers["cache-control"] == "private, no-store"
    assert file_response.headers["pragma"] == "no-cache"

    download = alice_client.get(f"{API}/assets/{asset['id']}/download")
    assert download.status_code == 200
    assert download.content == PNG_BYTES
    assert "attachment" in download.headers["content-disposition"]

    assert bob_client.get(f"{API}/assets/{asset['id']}/file").status_code == 404
    assert bob_client.get(f"{API}/assets/{asset['id']}/download").status_code == 404

    profile = alice_client.patch(
        f"{API}/me/profile", json={"avatar_asset_id": asset["id"]}
    )
    assert profile.status_code == 200
    assert profile.json()["avatar_asset_id"] == asset["id"]
    assert bob_client.patch(
        f"{API}/me/profile", json={"avatar_asset_id": asset["id"]}
    ).status_code == 404

    document = create_document(alice_client, "Image Document")
    saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={"blocks": [image_block(asset["id"], "diagram")]},
    )
    assert saved.status_code == 200
    assert saved.json()["blocks"][0]["asset_id"] == asset["id"]

    bad_type = alice_client.post(
        f"{API}/assets",
        files={"file": ("bad.txt", b"text", "text/plain")},
    )
    assert bad_type.status_code == 415

    empty = alice_client.post(
        f"{API}/assets",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert empty.status_code == 422


def test_recycle_and_restore_keep_id_and_ownership(
    alice_client, bob_client
):
    chapter = create_chapter(alice_client, "Recycle Chapter")
    d1 = create_document(
        alice_client, "Recycled One", chapter_id=chapter["id"]
    )
    d2 = create_document(
        alice_client, "Recycled Two", chapter_id=chapter["id"]
    )
    saved = alice_client.put(
        f"{API}/documents/{d1['id']}/blocks",
        headers=version_headers(d1["version"]),
        json={"blocks": [rich_text_block("kept through recycle")]},
    )
    assert saved.status_code == 200
    alice_client.put(f"{API}/documents/{d1['id']}/favorite")

    assert alice_client.get(f"{API}/favorites/count").json() == {"count": 1}
    assert alice_client.delete(f"{API}/documents/{d1['id']}").status_code == 204
    assert alice_client.get(f"{API}/documents/{d1['id']}").status_code == 404
    assert alice_client.get(f"{API}/favorites/count").json() == {"count": 0}

    library = alice_client.get(
        f"{API}/documents", params={"scope": "library"}
    ).json()
    assert [item["id"] for item in library] == [d2["id"]]

    recycle = alice_client.get(f"{API}/recycle")
    assert recycle.status_code == 200
    recycle_items = recycle.json()
    assert [item["document_id"] for item in recycle_items] == [d1["id"]]
    assert recycle_items[0]["original_chapter_id"] == chapter["id"]
    assert bob_client.get(f"{API}/recycle").json() == []

    restored = alice_client.post(
        f"{API}/recycle/{recycle_items[0]['id']}/restore", json={}
    )
    assert restored.status_code == 200
    assert restored.json()["id"] == d1["id"]
    assert restored.json()["chapter_id"] == chapter["id"]
    assert restored.json()["blocks"][0]["content"] == rich_text_block(
        "kept through recycle"
    )["content"]
    assert alice_client.get(f"{API}/favorites/count").json() == {"count": 0}

    library = alice_client.get(
        f"{API}/documents", params={"scope": "library"}
    ).json()
    assert [item["id"] for item in library] == [d2["id"], d1["id"]]
    chapter_docs = alice_client.get(
        f"{API}/documents",
        params={"scope": "chapter", "chapter_id": chapter["id"]},
    ).json()
    assert [item["id"] for item in chapter_docs] == [d2["id"], d1["id"]]

    assert alice_client.delete(f"{API}/chapters/{chapter['id']}").status_code == 204
    assert alice_client.delete(f"{API}/documents/{d2['id']}").status_code == 204
    recycle_two = alice_client.get(f"{API}/recycle").json()
    assert len(recycle_two) == 1
    restored_two = alice_client.post(
        f"{API}/recycle/{recycle_two[0]['id']}/restore", json={}
    )
    assert restored_two.status_code == 200
    assert restored_two.json()["id"] == d2["id"]
    assert restored_two.json()["chapter_id"] is None
    assert get_document(alice_client, d2["id"])["id"] == d2["id"]

def test_purge_keeps_asset_referenced_from_body_table_and_remark(
    alice,
    alice_client,
    db_session,
):
    asset = upload_asset(alice_client, name="shared-inline.png")
    asset_url = f"/c/api/v1/assets/{asset['id']}/file"

    image_document = create_document(alice_client, "Image Module Owner")
    saved_image = alice_client.put(
        f"{API}/documents/{image_document['id']}/blocks",
        headers=version_headers(image_document["version"]),
        json={"blocks": [image_block(asset["id"], "module")]},
    )
    assert saved_image.status_code == 200, saved_image.text

    body_document = create_document(alice_client, "Body Inline Owner")
    saved_body = alice_client.put(
        f"{API}/documents/{body_document['id']}/blocks",
        headers=version_headers(body_document["version"]),
        json={
            "blocks": [
                {
                    "block_type": "rich_text",
                    "content": {
                        "module": "paragraph",
                        "markdown": f"![正文]({asset_url})",
                    },
                    "asset_id": None,
                },
                {
                    "block_type": "rich_text",
                    "content": {
                        "module": "table",
                        "headers": ["图片"],
                        "rows": [[f"![表格]({asset_url})"]],
                    },
                    "asset_id": None,
                },
            ]
        },
    )
    assert saved_body.status_code == 200, saved_body.text

    remark_document = create_document(
        alice_client,
        "Remark Inline Owner",
        kind="source",
        language="c",
    )
    saved_remark = alice_client.put(
        f"{API}/documents/{remark_document['id']}/blocks",
        headers=version_headers(remark_document["version"]),
        json={
            "blocks": [
                {
                    "block_type": "code",
                    "content": {"text": "int main(void) { return 0; }", "language": "c"},
                    "asset_id": None,
                },
                {
                    "block_type": "remark",
                    "content": {
                        "module": "paragraph",
                        "markdown": f"![备注]({asset_url})",
                    },
                    "asset_id": None,
                },
            ]
        },
    )
    assert saved_remark.status_code == 200, saved_remark.text

    assert alice_client.delete(
        f"{API}/documents/{image_document['id']}"
    ).status_code == 204
    entry = db_session.scalar(
        select(RecycleEntry).where(
            RecycleEntry.document_id == image_document["id"]
        )
    )
    document = db_session.get(Document, image_document["id"])
    assert entry is not None and document is not None
    old = utcnow() - timedelta(days=30)
    entry.deleted_at = old
    document.deleted_at = old
    db_session.commit()

    assert purge_expired_recycle(db_session, alice.id) == 1
    assert db_session.get(Asset, asset["id"]) is not None
    assert alice_client.get(
        f"{API}/assets/{asset['id']}/file"
    ).status_code == 200
    assert alice_client.get(
        f"{API}/documents/{body_document['id']}"
    ).status_code == 200
    assert alice_client.get(
        f"{API}/documents/{remark_document['id']}"
    ).status_code == 200


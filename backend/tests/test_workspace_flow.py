from datetime import timedelta
from pathlib import Path

from sqlalchemy import update

from app.config import get_settings
from app.models import Asset, Document, RecycleEntry
from app.security import utcnow
from helpers import (
    PNG_BYTES,
    API,
    create_chapter,
    create_document,
    error_code,
    get_document,
    image_block,
    rich_text_block,
    upload_asset,
    version_headers,
)


def test_workspace_summary_and_import_markdown_source(
    alice, alice_client, bob_client
):
    workspace = alice_client.get(f"{API}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()
    assert payload["user"]["display_name"] == "Alice"
    assert payload["chapters"] == []
    assert payload["library_count"] == 0
    assert payload["favorite_count"] == 0
    assert payload["recycle_count"] == 0
    assert payload["storage"] == {"asset_count": 0, "total_bytes": 0}
    assert payload["recycle_retention_days"] == 7

    chapter = create_chapter(alice_client, "导入章节")
    markdown = """# 指针笔记

这是 **加粗** 和 [链接](https://example.com)。

- 第一项
- 第二项

```c
int main(void) { return 0; }
```

| 名称 | 值 |
| --- | --- |
| a | 1 |
"""
    response = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("pointer.md", markdown.encode(), "text/markdown")},
        data={"chapter_id": str(chapter["id"])},
    )
    assert response.status_code == 201, response.text
    imported = response.json()
    assert imported["id"] > 0
    assert imported["title"] == "指针笔记"
    assert imported["kind"] == "note"
    assert imported["chapter_id"] == chapter["id"]
    assert [block["block_type"] for block in imported["blocks"]] == [
        "rich_text",
        "rich_text",
        "rich_text",
        "code",
        "rich_text",
    ]
    assert [
        block["content"].get("module") for block in imported["blocks"]
    ] == ["heading1", "paragraph", "bullet_list", None, "table"]
    assert imported["summary"] == "指针笔记"
    assert imported["blocks"][4]["content"]["headers"] == ["名称", "值"]

    source = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("demo.c", b"int main(void) { return 0; }\n", "text/plain")},
        data={"title": "示例 C"},
    )
    assert source.status_code == 201, source.text
    source_payload = source.json()
    assert source_payload["kind"] == "source"
    assert source_payload["language"] == "c"
    assert source_payload["blocks"][0]["content"]["language"] == "c"

    header = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("demo.h", b"#define ANSWER 42\n", "text/plain")},
    )
    assert header.status_code == 201, header.text
    assert header.json()["language"] == "h"

    assert bob_client.get(f"{API}/documents/{imported['id']}").status_code == 404
    cross_chapter = bob_client.post(
        f"{API}/documents/import",
        files={"file": ("bob.md", b"# Bob", "text/markdown")},
        data={"chapter_id": str(chapter["id"])},
    )
    assert cross_chapter.status_code == 404

    duplicate = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("pointer.md", markdown.encode(), "text/markdown")},
    )
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "document_name_conflict"

    bad_type = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("bad.txt", b"hello", "text/plain")},
    )
    assert bad_type.status_code == 415

    summary = alice_client.get(f"{API}/workspace").json()
    assert summary["library_count"] == 3
    assert summary["chapters"][0]["document_count"] == 1

    delete_source = alice_client.delete(f"{API}/documents/{source_payload['id']}")
    assert delete_source.status_code == 204
    summary = alice_client.get(f"{API}/workspace").json()
    assert summary["library_count"] == 2
    assert summary["recycle_count"] == 1


def test_import_splits_todo_formula_and_private_image_modules(
    alice_client, bob_client
):
    asset = upload_asset(alice_client, name="plot.png")
    markdown = f"""## 导入二

- [ ] 未完成
- [x] 已完成

$$
E = mc^2
$$

![图](/c/api/v1/assets/{asset['id']}/file "说明")
"""
    response = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("advanced.md", markdown.encode(), "text/markdown")},
    )
    assert response.status_code == 201, response.text
    blocks = response.json()["blocks"]
    assert [
        block["content"].get("module") for block in blocks
    ] == ["heading2", "todo_list", None, None]
    assert [block["block_type"] for block in blocks] == [
        "rich_text",
        "rich_text",
        "formula",
        "image",
    ]
    assert blocks[2]["content"]["latex"] == "E = mc^2"
    assert blocks[3]["asset_id"] == asset["id"]
    assert blocks[3]["content"] == {"alt": "图", "caption": "说明"}

    bob_asset = upload_asset(bob_client, name="bob.png")
    denied = alice_client.post(
        f"{API}/documents/import",
        files={
            "file": (
                "bob-image.md",
                f"![x](/c/api/v1/assets/{bob_asset['id']}/file)\n".encode(),
                "text/markdown",
            )
        },
    )
    assert denied.status_code == 404


def test_recycle_retention_and_asset_reference_guard(
    alice_client, bob_client, db_session
):
    chapter = create_chapter(alice_client, "回收章节")
    active = create_document(
        alice_client, "仍在引用", chapter_id=chapter["id"]
    )
    recycled = create_document(
        alice_client, "将被清理", chapter_id=chapter["id"]
    )
    shared_asset = upload_asset(alice_client, name="shared.png")
    orphan_asset = upload_asset(alice_client, name="orphan.png")
    settings = get_settings()
    orphan_path = (
        settings.uploads_path
        / str(alice_client.get(f"{API}/me").json()["id"])
        / _asset_storage_name(db_session, orphan_asset["id"])
    )
    assert orphan_path.exists()

    saved_active = alice_client.put(
        f"{API}/documents/{active['id']}/blocks",
        headers=version_headers(active["version"]),
        json={"blocks": [image_block(shared_asset["id"])]},
    )
    assert saved_active.status_code == 200, saved_active.text
    saved_recycled = alice_client.put(
        f"{API}/documents/{recycled['id']}/blocks",
        headers=version_headers(recycled["version"]),
        json={
            "blocks": [
                rich_text_block("kept"),
                image_block(shared_asset["id"]),
                image_block(orphan_asset["id"]),
            ]
        },
    )
    assert saved_recycled.status_code == 200, saved_recycled.text
    assert alice_client.put(
        f"{API}/documents/{recycled['id']}/favorite"
    ).status_code == 204
    assert alice_client.delete(
        f"{API}/documents/{recycled['id']}"
    ).status_code == 204

    recycle = alice_client.get(f"{API}/recycle")
    assert recycle.status_code == 200, recycle.text
    item = recycle.json()[0]
    assert item["document_id"] == recycled["id"]
    assert item["original_chapter_name"] == "回收章节"
    assert item["days_remaining"] == 7
    assert item["expires_at"]

    old = utcnow() - timedelta(days=settings.recycle_retention_days + 1)
    db_session.execute(
        update(RecycleEntry)
        .where(RecycleEntry.id == item["id"])
        .values(deleted_at=old)
    )
    db_session.execute(
        update(Document)
        .where(Document.id == recycled["id"])
        .values(deleted_at=old)
    )
    db_session.commit()

    workspace = alice_client.get(f"{API}/workspace")
    assert workspace.status_code == 200, workspace.text
    summary = workspace.json()
    assert summary["recycle_count"] == 0
    assert summary["library_count"] == 1
    assert summary["favorite_count"] == 0
    assert summary["storage"]["asset_count"] == 1
    assert summary["storage"]["total_bytes"] == len(PNG_BYTES)
    assert alice_client.get(
        f"{API}/assets/{shared_asset['id']}/file"
    ).status_code == 200
    assert alice_client.get(
        f"{API}/assets/{orphan_asset['id']}/file"
    ).status_code == 404
    assert not orphan_path.exists()
    assert alice_client.get(f"{API}/recycle").json() == []
    assert alice_client.post(
        f"{API}/recycle/{item['id']}/restore", json={}
    ).status_code == 404
    assert alice_client.get(f"{API}/recycle").json() == []
    assert bob_client.get(f"{API}/workspace").json()["recycle_count"] == 0


def _asset_storage_name(db_session, asset_id: int) -> str:
    asset = db_session.get(Asset, asset_id)
    assert asset is not None
    return asset.storage_name


def test_restore_name_conflict_uses_new_title_and_keeps_stable_id(
    alice_client,
):
    chapter = create_chapter(alice_client, "恢复章节")
    document = create_document(
        alice_client, "冲突文档", chapter_id=chapter["id"]
    )
    saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={"blocks": [rich_text_block("正文保留")]},
    )
    assert saved.status_code == 200
    assert alice_client.put(
        f"{API}/documents/{document['id']}/favorite"
    ).status_code == 204
    assert alice_client.delete(
        f"{API}/documents/{document['id']}"
    ).status_code == 204
    create_document(alice_client, "冲突文档")

    recycle = alice_client.get(f"{API}/recycle").json()
    entry = recycle[0]
    conflict = alice_client.post(
        f"{API}/recycle/{entry['id']}/restore", json={}
    )
    assert conflict.status_code == 409
    assert error_code(conflict) == "document_name_conflict"

    restored = alice_client.post(
        f"{API}/recycle/{entry['id']}/restore",
        json={"title": "冲突文档（恢复）"},
    )
    assert restored.status_code == 200, restored.text
    payload = restored.json()
    assert payload["id"] == document["id"]
    assert payload["title"] == "冲突文档（恢复）"
    assert payload["chapter_id"] == chapter["id"]
    assert payload["blocks"][0]["content"] == rich_text_block("正文保留")[
        "content"
    ]
    assert payload["is_favorite"] is False
    assert alice_client.get(
        f"{API}/documents/{document['id']}"
    ).json()["id"] == document["id"]

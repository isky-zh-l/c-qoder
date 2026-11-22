from helpers import (
    API,
    create_document,
    get_document,
    upload_asset,
    version_headers,
)
from app.services.source import join_source_code


def code_block(text: str) -> dict:
    return {
        "block_type": "code",
        "content": {"text": text, "language": "c"},
        "asset_id": None,
    }


def remark_block(markdown: str) -> dict:
    return {
        "block_type": "remark",
        "content": {"module": "paragraph", "markdown": markdown},
        "asset_id": None,
    }


def result_block(text: str) -> dict:
    return {
        "block_type": "result",
        "content": {"text": text},
        "asset_id": None,
    }


def image_block(asset_id: int, caption: str) -> dict:
    return {
        "block_type": "image",
        "content": {"alt": "内存图", "caption": caption},
        "asset_id": asset_id,
    }


def test_source_join_rule_preserves_content_and_avoids_glued_statements():
    first = "#include <stdio.h>\n\nint main(void) {\n    // 中文注释"
    second = "    int value = 42;\n    return value;\n}"
    assert join_source_code([first, second]) == f"{first}\n{second}"
    assert join_source_code([first + "\n", second]) == f"{first}\n{second}"
    assert join_source_code(["", first, "", second]) == f"{first}\n{second}"
    assert join_source_code(["a;\n\n", "b;\n"]) == "a;\n\nb;\n"
    assert join_source_code(["", ""]) == ""


def test_source_modules_download_version_and_ownership(
    alice_client, bob_client
):
    document = create_document(
        alice_client,
        "源码编辑验收",
        kind="source",
        language="c",
    )
    asset = upload_asset(alice_client, name="memory.png")
    code_one = "#include <stdio.h>\n\nint main(void) {\n    // 中文注释"
    code_two = "    int value = 42;\n    return value;\n}"
    blocks = [
        code_block(code_one),
        remark_block("**中文样式备注** <u>下划线</u> ==高亮=="),
        result_block("程序输出：\n你好\n\n结束\n"),
        code_block(code_two),
        image_block(asset["id"], "第一次说明"),
    ]
    saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(1),
        json={"blocks": blocks},
    )
    assert saved.status_code == 200, saved.text
    saved_payload = saved.json()
    ids = [block["id"] for block in saved_payload["blocks"]]
    assert [block["block_type"] for block in saved_payload["blocks"]] == [
        "code",
        "remark",
        "result",
        "code",
        "image",
    ]
    assert saved_payload["version"] == 2
    expected_source = f"{code_one}\n{code_two}"

    download = alice_client.get(f"{API}/documents/{document['id']}/download")
    assert download.status_code == 200
    assert download.content.decode("utf-8") == expected_source
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["content-type"].startswith("text/plain")

    # 只改运行结果，源码不变，但版本必须更新。
    updated_blocks = []
    for block in saved_payload["blocks"]:
        item = {
            "id": block["id"],
            "block_type": block["block_type"],
            "content": block["content"],
            "asset_id": block["asset_id"],
        }
        if block["block_type"] == "result":
            item["content"] = {"text": "程序输出：\n你好\n\n结束\n退出码 0\n"}
        updated_blocks.append(item)
    second = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(saved_payload["version"]),
        json={"blocks": updated_blocks},
    )
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 3
    assert [block["id"] for block in second.json()["blocks"]] == ids
    assert alice_client.get(
        f"{API}/documents/{document['id']}/download"
    ).content.decode("utf-8") == expected_source

    # 换序并把代码二放到代码一前面；ID 保持稳定，下载内容按新顺序。
    reordered = [
        updated_blocks[3],
        updated_blocks[0],
        updated_blocks[1],
        updated_blocks[2],
        {**updated_blocks[4], "content": {"alt": "内存图", "caption": "换序说明"}},
    ]
    third = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(second.json()["version"]),
        json={"blocks": reordered},
    )
    assert third.status_code == 200, third.text
    assert [block["id"] for block in third.json()["blocks"]] == [
        ids[3],
        ids[0],
        ids[1],
        ids[2],
        ids[4],
    ]
    assert alice_client.get(
        f"{API}/documents/{document['id']}/download"
    ).content.decode("utf-8") == f"{code_two}\n{code_one}"

    # 只改备注，源码不变，版本继续更新且 ID 不变。
    remark_only = []
    for block in third.json()["blocks"]:
        item = {
            "id": block["id"],
            "block_type": block["block_type"],
            "content": block["content"],
            "asset_id": block["asset_id"],
        }
        if block["block_type"] == "remark":
            item["content"] = {
                "module": "paragraph",
                "markdown": "**备注已更新** <u>仍然有样式</u>",
            }
        remark_only.append(item)
    fourth = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(third.json()["version"]),
        json={"blocks": remark_only},
    )
    assert fourth.status_code == 200, fourth.text
    assert fourth.json()["version"] == 5
    assert [block["id"] for block in fourth.json()["blocks"]] == [
        ids[3],
        ids[0],
        ids[1],
        ids[2],
        ids[4],
    ]
    assert alice_client.get(
        f"{API}/documents/{document['id']}/download"
    ).content.decode("utf-8") == f"{code_two}\n{code_one}"

    assert bob_client.get(f"{API}/documents/{document['id']}").status_code == 404
    assert bob_client.get(
        f"{API}/documents/{document['id']}/download"
    ).status_code == 404
    assert bob_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(third.json()["version"]),
        json={"blocks": [code_block("int hacked;")]},
    ).status_code == 404
    assert bob_client.get(f"{API}/assets/{asset['id']}/file").status_code == 404
    assert bob_client.get(
        f"{API}/assets/{asset['id']}/download"
    ).status_code == 404
    assert get_document(alice_client, document["id"])["kind"] == "source"


def test_imported_source_is_complete_code_and_note_cannot_download(
    alice_client
):
    source = b'#include <stdio.h>\n\nint main(void) {\n    return 0;\n}\n'
    imported = alice_client.post(
        f"{API}/documents/import",
        files={"file": ("main.c", source, "text/plain")},
    )
    assert imported.status_code == 201, imported.text
    blocks = imported.json()["blocks"]
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == "code"
    assert blocks[0]["content"]["text"].encode() == source
    download = alice_client.get(
        f"{API}/documents/{imported.json()['id']}/download"
    )
    assert download.status_code == 200
    assert download.content == source

    note = create_document(alice_client, "普通笔记下载")
    assert alice_client.get(
        f"{API}/documents/{note['id']}/download"
    ).status_code == 404

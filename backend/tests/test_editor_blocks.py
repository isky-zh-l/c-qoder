from helpers import (
    API,
    create_document,
    error_code,
    get_document,
    upload_asset,
    version_headers,
)


def text_module(module: str, markdown: str) -> dict:
    return {
        "block_type": "rich_text",
        "content": {"module": module, "markdown": markdown},
        "asset_id": None,
    }


def code_module(text: str = "int main(void) { return 0; }") -> dict:
    return {
        "block_type": "code",
        "content": {"text": text, "language": "c"},
        "asset_id": None,
    }


def formula_module(latex: str = "E = mc^2") -> dict:
    return {
        "block_type": "formula",
        "content": {"latex": latex},
        "asset_id": None,
    }


def test_block_ids_stay_stable_and_removed_ids_are_deleted(
    alice_client, bob_client
):
    document = create_document(alice_client, "Stable Blocks")
    first_save = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={
            "blocks": [
                text_module("paragraph", "第一段"),
                formula_module("x^2"),
            ]
        },
    )
    assert first_save.status_code == 200, first_save.text
    original = first_save.json()["blocks"]
    first_id, second_id = [block["id"] for block in original]

    second_save = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(first_save.json()["version"]),
        json={
            "blocks": [
                {
                    **text_module("paragraph", "第一段已修改"),
                    "id": first_id,
                },
                {
                    **formula_module("y^3"),
                    "id": second_id,
                },
                code_module("int x = 1;"),
            ]
        },
    )
    assert second_save.status_code == 200, second_save.text
    blocks = second_save.json()["blocks"]
    assert [block["id"] for block in blocks[:2]] == [first_id, second_id]
    assert blocks[0]["content"]["markdown"] == "第一段已修改"
    assert blocks[2]["id"] not in {first_id, second_id}
    third_id = blocks[2]["id"]

    third_save = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(second_save.json()["version"]),
        json={"blocks": [{**text_module("paragraph", "只保留第一块"), "id": first_id}]},
    )
    assert third_save.status_code == 200, third_save.text
    kept = third_save.json()["blocks"]
    assert [block["id"] for block in kept] == [first_id]
    assert third_id not in {block["id"] for block in kept}

    bob_document = create_document(bob_client, "Bob Blocks")
    bob_saved = bob_client.put(
        f"{API}/documents/{bob_document['id']}/blocks",
        headers=version_headers(bob_document["version"]),
        json={"blocks": [text_module("paragraph", "Bob block")]},
    )
    bob_block_id = bob_saved.json()["blocks"][0]["id"]

    cross_user = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(third_save.json()["version"]),
        json={
            "blocks": [
                {**text_module("paragraph", "偷用块"), "id": bob_block_id}
            ]
        },
    )
    assert cross_user.status_code == 404

    duplicate = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(third_save.json()["version"]),
        json={
            "blocks": [
                {**text_module("paragraph", "A"), "id": first_id},
                {**text_module("paragraph", "B"), "id": first_id},
            ]
        },
    )
    assert duplicate.status_code == 422

    create_with_id = alice_client.post(
        f"{API}/documents",
        json={
            "kind": "note",
            "title": "No Existing IDs",
            "chapter_id": None,
        },
    )
    assert create_with_id.status_code == 201
    invalid_create = alice_client.put(
        f"{API}/documents/{create_with_id.json()['id']}/blocks",
        headers=version_headers(create_with_id.json()["version"]),
        json={
            "blocks": [
                {**text_module("paragraph", "new"), "id": first_id}
            ]
        },
    )
    assert invalid_create.status_code == 404


def test_markdown_and_module_security_validation(alice_client):
    document = create_document(alice_client, "Markdown Security")

    allowed = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={
            "blocks": [
                text_module(
                    "paragraph",
                    '**粗体** *斜体* <u>下划线</u> ~~删除~~ `code` '
                    '<mark data-tone="purple">紫色</mark> ==黄色== '
                    "[链接](https://example.com) $x^2$",
                ),
                {
                    "block_type": "rich_text",
                    "content": {
                        "module": "table",
                        "headers": ["名称", "说明"],
                        "rows": [["`int`", "<u>整数</u>"]],
                    },
                    "asset_id": None,
                },
                code_module("<script>alert(1)</script>\n    indented"),
                formula_module("<script>alert(1)</script>"),
            ]
        },
    )
    assert allowed.status_code == 200, allowed.text
    saved = get_document(alice_client, document["id"])
    assert saved["blocks"][0]["content"]["module"] == "paragraph"

    cases = [
        text_module("paragraph", "<script>alert(1)</script>"),
        text_module("paragraph", '<mark data-tone="red">bad</mark>'),
        text_module("paragraph", "[bad](javascript:alert(1))"),
        text_module("paragraph", "![remote](https://example.com/x.png)"),
        text_module("paragraph", '<iframe src="x"></iframe>'),
        {
            "block_type": "rich_text",
            "content": {
                "module": "table",
                "headers": ["a"],
                "rows": [["<script>x</script>"]],
            },
            "asset_id": None,
        },
        {
            "block_type": "rich_text",
            "content": {"module": "unknown", "markdown": "x"},
            "asset_id": None,
        },
    ]
    version = saved["version"]
    for payload in cases:
        response = alice_client.put(
            f"{API}/documents/{document['id']}/blocks",
            headers=version_headers(version),
            json={"blocks": [payload]},
        )
        assert response.status_code == 422, (payload, response.text)
        assert error_code(response) == "validation_error"
        assert get_document(alice_client, document["id"])["version"] == version


def test_markdown_image_asset_ownership(alice_client, bob_client):
    document = create_document(alice_client, "Markdown Image Ownership")
    own_asset = upload_asset(alice_client, name="own.png")
    own_saved = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(document["version"]),
        json={
            "blocks": [
                text_module(
                    "paragraph",
                    f'![own](/c/api/v1/assets/{own_asset["id"]}/file "说明")',
                )
            ]
        },
    )
    assert own_saved.status_code == 200, own_saved.text
    bob_asset = upload_asset(bob_client, name="bob.png")
    version = own_saved.json()["version"]
    denied = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(version),
        json={
            "blocks": [
                text_module(
                    "paragraph",
                    f'![bob](/c/api/v1/assets/{bob_asset["id"]}/file)',
                )
            ]
        },
    )
    assert denied.status_code == 404
    assert get_document(alice_client, document["id"])["version"] == version

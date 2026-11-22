from helpers import (
    API,
    PASSWORD_ALICE,
    code_block,
    create_chapter,
    create_document,
    error_code,
    get_document,
    image_block,
    rich_text_block,
    upload_asset,
    version_headers,
)


def test_library_chapter_and_favorite_orders_are_independent(alice_client):
    chapter_one = create_chapter(alice_client, "Chapter One")
    chapter_two = create_chapter(alice_client, "Chapter Two")

    d1 = create_document(
        alice_client, "Doc 1", chapter_id=chapter_one["id"]
    )
    d2 = create_document(
        alice_client, "Doc 2", chapter_id=chapter_one["id"]
    )
    d3 = create_document(
        alice_client, "Doc 3", chapter_id=chapter_two["id"]
    )
    d4 = create_document(alice_client, "Doc 4")

    def ids(scope: str = "library", chapter_id: int | None = None):
        params = {"scope": scope}
        if chapter_id is not None:
            params["chapter_id"] = chapter_id
        response = alice_client.get(f"{API}/documents", params=params)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()]

    assert ids() == [d1["id"], d2["id"], d3["id"], d4["id"]]

    response = alice_client.put(
        f"{API}/orders/library",
        json={"document_ids": [d3["id"], d1["id"], d4["id"], d2["id"]]},
    )
    assert response.status_code == 204
    assert ids() == [d3["id"], d1["id"], d4["id"], d2["id"]]

    response = alice_client.put(
        f"{API}/orders/chapters/{chapter_one['id']}",
        json={"document_ids": [d2["id"], d1["id"]]},
    )
    assert response.status_code == 204
    assert ids("chapter", chapter_one["id"]) == [d2["id"], d1["id"]]

    assert alice_client.put(f"{API}/documents/{d1['id']}/favorite").status_code == 204
    assert alice_client.put(f"{API}/documents/{d3['id']}/favorite").status_code == 204
    assert alice_client.get(f"{API}/favorites/count").json() == {"count": 2}
    assert ids("favorites") == [d1["id"], d3["id"]]

    # Favoriting does not change either normal order.
    assert ids() == [d3["id"], d1["id"], d4["id"], d2["id"]]
    assert ids("chapter", chapter_one["id"]) == [d2["id"], d1["id"]]

    response = alice_client.put(
        f"{API}/orders/favorites",
        json={"document_ids": [d3["id"], d1["id"]]},
    )
    assert response.status_code == 204
    assert ids("favorites") == [d3["id"], d1["id"]]
    assert ids() == [d3["id"], d1["id"], d4["id"], d2["id"]]

    missing = alice_client.put(
        f"{API}/orders/library",
        json={"document_ids": [d3["id"], d1["id"], d4["id"]]},
    )
    assert missing.status_code == 409
    assert error_code(missing) == "order_conflict"
    assert ids() == [d3["id"], d1["id"], d4["id"], d2["id"]]

    duplicate = alice_client.put(
        f"{API}/orders/favorites",
        json={"document_ids": [d3["id"], d3["id"], d1["id"]]},
    )
    assert duplicate.status_code == 409
    assert ids("favorites") == [d3["id"], d1["id"]]

    missing_chapter = alice_client.get(
        f"{API}/documents", params={"scope": "chapter"}
    )
    assert missing_chapter.status_code == 422

    unknown_chapter = alice_client.get(
        f"{API}/documents",
        params={"scope": "chapter", "chapter_id": 99999},
    )
    assert unknown_chapter.status_code == 404


def test_modules_metadata_atomic_save_and_two_device_conflict(
    alice,
    alice_client,
    bob_client,
    login_as,
):
    chapter_one = create_chapter(alice_client, "One")
    chapter_two = create_chapter(alice_client, "Two")
    document = create_document(
        alice_client, "Atomic Document", chapter_id=chapter_one["id"]
    )
    take_name = create_document(alice_client, "Taken")
    asset = upload_asset(alice_client)
    second_device = login_as(alice.email, PASSWORD_ALICE)

    before = get_document(alice_client, document["id"])
    assert before["version"] == 1

    response = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(before["version"]),
        json={
            "title": "Edited",
            "chapter_id": chapter_two["id"],
            "blocks": [
                rich_text_block("edited content"),
                image_block(asset["id"]),
            ],
        },
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["version"] == 2
    assert saved["title"] == "Edited"
    assert saved["chapter_id"] == chapter_two["id"]
    assert len(saved["blocks"]) == 2
    assert saved["summary"] == "edited content"

    stale = second_device.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(1),
        json={
            "title": "Stale Device",
            "blocks": [rich_text_block("stale content")],
        },
    )
    assert stale.status_code == 409
    assert error_code(stale) == "version_conflict"
    assert stale.json()["error"]["details"]["current_version"] == 2

    still_saved = get_document(second_device, document["id"])
    assert still_saved["version"] == 2
    assert still_saved["title"] == "Edited"
    assert still_saved["blocks"][0]["content"] == rich_text_block(
        "edited content"
    )["content"]
    assert still_saved["chapter_id"] == chapter_two["id"]

    retry = second_device.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(still_saved["version"]),
        json={
            "title": "Second Device",
            "blocks": [rich_text_block("second content")],
        },
    )
    assert retry.status_code == 200
    assert retry.json()["version"] == 3
    assert retry.json()["title"] == "Second Device"

    atomic_conflict = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(retry.json()["version"]),
        json={
            "title": "Taken",
            "blocks": [rich_text_block("must not persist")],
        },
    )
    assert atomic_conflict.status_code == 409
    assert error_code(atomic_conflict) == "document_name_conflict"

    unchanged = get_document(alice_client, document["id"])
    assert unchanged["version"] == 3
    assert unchanged["title"] == "Second Device"
    assert len(unchanged["blocks"]) == 1
    assert unchanged["blocks"][0]["content"] == rich_text_block(
        "second content"
    )["content"]

    missing_header = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        json={"blocks": [rich_text_block("missing header")]},
    )
    assert missing_header.status_code == 428

    metadata = alice_client.patch(
        f"{API}/documents/{document['id']}",
        headers=version_headers(unchanged["version"]),
        json={"title": "Patched", "chapter_id": chapter_one["id"]},
    )
    assert metadata.status_code == 200
    assert metadata.json()["version"] == 4
    assert metadata.json()["title"] == "Patched"
    assert metadata.json()["chapter_id"] == chapter_one["id"]

    bob_doc = create_document(bob_client, "Bob Atomic")
    cross_asset = bob_client.put(
        f"{API}/documents/{bob_doc['id']}/blocks",
        headers=version_headers(bob_doc["version"]),
        json={"blocks": [image_block(asset["id"])]},
    )
    assert cross_asset.status_code == 404
    bob_after = get_document(bob_client, bob_doc["id"])
    assert bob_after["version"] == 1
    assert bob_after["blocks"] == []

    source = create_document(
        alice_client, "source.c", kind="source", language="c"
    )
    source_saved = alice_client.put(
        f"{API}/documents/{source['id']}/blocks",
        headers=version_headers(source["version"]),
        json={
            "blocks": [
                code_block("int main(void) { return 0; }"),
                {
                    "block_type": "remark",
                    "content": rich_text_block("styled remark")["content"],
                    "asset_id": None,
                },
                {"block_type": "result", "content": {"text": "exit 0"}, "asset_id": None},
                image_block(asset["id"]),
            ]
        },
    )
    assert source_saved.status_code == 200, source_saved.text
    assert [b["block_type"] for b in source_saved.json()["blocks"]] == [
        "code",
        "remark",
        "result",
        "image",
    ]

    invalid_note_block = alice_client.put(
        f"{API}/documents/{document['id']}/blocks",
        headers=version_headers(metadata.json()["version"]),
        json={
            "blocks": [
                {
                    "block_type": "remark",
                    "content": {"type": "doc", "content": []},
                    "asset_id": None,
                }
            ]
        },
    )
    assert invalid_note_block.status_code == 422

    assert take_name["id"] != document["id"]

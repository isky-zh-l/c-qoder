import base64
import email
import re
from email import policy
from email.message import EmailMessage
from typing import Any
from urllib.parse import unquote

API = "/c/api/v1"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOsCDjBwMDAxAAGABKaAZSwwH1lAAAAAElFTkSuQmCC"
)
PASSWORD_ALICE = "alice-password-123"
PASSWORD_BOB = "bob-password-12345"
PASSWORD_ADMIN = "admin-password-123"
PASSWORD_EXTRA = "carol-password-123"


def version_headers(version: int) -> dict[str, str]:
    return {"If-Match": str(version)}


def error_code(response) -> str:
    return response.json()["error"]["code"]


def create_chapter(client, name: str = "章节") -> dict[str, Any]:
    response = client.post(f"{API}/chapters", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_document(
    client,
    title: str,
    *,
    kind: str = "note",
    chapter_id: int | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": kind, "title": title, "chapter_id": chapter_id}
    if language is not None:
        payload["language"] = language
    response = client.post(f"{API}/documents", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def upload_asset(
    client,
    *,
    name: str = "diagram.png",
    mime_type: str = "image/png",
    data: bytes = PNG_BYTES,
) -> dict[str, Any]:
    response = client.post(
        f"{API}/assets",
        files={"file": (name, data, mime_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def rich_text_block(text: str = "hello") -> dict[str, Any]:
    return {
        "block_type": "rich_text",
        "content": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        },
        "asset_id": None,
    }


def code_block(text: str = "int main(void) { return 0; }") -> dict[str, Any]:
    return {
        "block_type": "code",
        "content": {"text": text, "language": "c"},
        "asset_id": None,
    }


def image_block(asset_id: int, alt: str = "image") -> dict[str, Any]:
    return {
        "block_type": "image",
        "content": {"alt": alt, "caption": ""},
        "asset_id": asset_id,
    }


def get_document(client, document_id: int) -> dict[str, Any]:
    response = client.get(f"{API}/documents/{document_id}")
    assert response.status_code == 200, response.text
    return response.json()


def register_user(
    client,
    email: str,
    password: str,
    display_name: str | None = None,
):
    payload: dict[str, Any] = {"email": email, "password": password}
    if display_name is not None:
        payload["display_name"] = display_name
    return client.post(f"{API}/auth/register", json=payload)


def latest_email_body(messages: list[bytes]) -> tuple[EmailMessage, str]:
    assert messages, "expected an email in the local SMTP mailbox"
    message = email.message_from_bytes(messages[-1], policy=policy.default)
    body_part = message.get_body(preferencelist=("plain",))
    assert body_part is not None
    return message, body_part.get_content()


def verification_token(messages: list[bytes]) -> str:
    _message, body = latest_email_body(messages)
    match = re.search(r"/verify-email\?token=([^\s<\"]+)", body)
    assert match, body
    return unquote(match.group(1))


def password_reset_token(messages: list[bytes]) -> str:
    _message, body = latest_email_body(messages)
    match = re.search(r"/reset-password\?token=([^\s<\"]+)", body)
    assert match, body
    return unquote(match.group(1))


def email_link(messages: list[bytes], path: str) -> str:
    _message, body = latest_email_body(messages)
    match = re.search(rf"(https?://\S+{re.escape(path)}\?token=\S+)", body)
    assert match, body
    return match.group(1).rstrip(".,)")

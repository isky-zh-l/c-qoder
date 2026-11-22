from __future__ import annotations

import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import (
    Asset,
    Block,
    Document,
    DocumentPublication,
    User,
    UserProfile,
)
from app.security import utcnow
from app.services.access import get_owned_document
from app.services.assets import asset_path
from app.services.content import block_asset_ids

settings = get_settings()

ASSET_URL_RE = re.compile(
    r"(?:https?://[^/\s\"')]+)?(?:/[^\s\"')]*)?/assets/(\d+)/file"
)
PUBLIC_ASSET_ID_RE = re.compile(r"/assets/(\d+)(?:$|[\s\"')])")


def _display_name(db: Session, user_id: int) -> str:
    profile = db.get(UserProfile, user_id)
    if profile is not None and profile.display_name.strip():
        return profile.display_name.strip()
    user = db.get(User, user_id)
    return user.email.split("@", 1)[0] if user is not None else "作者"


def _new_share_token(db: Session) -> str:
    for _ in range(5):
        token = secrets.token_urlsafe(32)
        exists = db.scalar(
            select(Document.id).where(Document.share_token == token)
        )
        if exists is None:
            return token
    raise ApiError(500, "internal_error", "无法生成分享令牌")


def _publicize_string(value: str, share_token: str) -> str:
    replacement = (
        f"{settings.api_base_path}/public/documents/{share_token}/assets/"
    )
    return ASSET_URL_RE.sub(lambda match: f"{replacement}{match.group(1)}", value)


def _publicize_content(value: Any, share_token: str) -> Any:
    if isinstance(value, str):
        return _publicize_string(value, share_token)
    if isinstance(value, list):
        return [_publicize_content(item, share_token) for item in value]
    if isinstance(value, dict):
        return {
            key: _publicize_content(item, share_token)
            for key, item in value.items()
        }
    return value


def _snapshot_blocks(
    db: Session, document: Document, share_token: str
) -> list[dict[str, Any]]:
    blocks = db.scalars(
        select(Block)
        .where(Block.document_id == document.id)
        .order_by(Block.sort_order, Block.id)
    ).all()
    result: list[dict[str, Any]] = []
    for block in blocks:
        content = block.content
        if block.block_type in ("rich_text", "remark"):
            content = _publicize_content(content, share_token)
        result.append(
            {
                "block_type": block.block_type,
                "content": content,
                "asset_id": block.asset_id,
                "sort_order": block.sort_order,
            }
        )
    return result


def publish_document(
    db: Session, user_id: int, document_id: int
) -> tuple[Document, DocumentPublication]:
    from app.services.storage import (
        compute_storage_usage,
        enforce_quota_after_change,
        lock_user_for_storage,
    )

    user = lock_user_for_storage(db, user_id)
    before_usage = compute_storage_usage(db, user_id, user=user)
    document = get_owned_document(db, user_id, document_id, for_update=True)
    now = utcnow()
    if document.visibility == "public" and document.share_token:
        share_token = document.share_token
    else:
        share_token = _new_share_token(db)

    publication = db.get(DocumentPublication, document.id)
    blocks = _snapshot_blocks(db, document, share_token)
    if publication is None:
        publication = DocumentPublication(
            document_id=document.id,
            owner_user_id=user_id,
            title=document.title,
            kind=document.kind,
            language=document.language,
            author_display_name=_display_name(db, user_id),
            published_at=now,
            source_version=document.version,
            blocks=blocks,
        )
        db.add(publication)
    else:
        publication.owner_user_id = user_id
        publication.title = document.title
        publication.kind = document.kind
        publication.language = document.language
        publication.author_display_name = _display_name(db, user_id)
        publication.published_at = now
        publication.source_version = document.version
        publication.blocks = blocks

    document.visibility = "public"
    document.share_token = share_token
    document.published_at = now
    try:
        enforce_quota_after_change(
            db,
            user,
            before_used_bytes=before_usage.used_bytes,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(document)
    db.refresh(publication)
    return document, publication


def unpublish_document(
    db: Session, user_id: int, document_id: int
) -> Document:
    document = get_owned_document(db, user_id, document_id, for_update=True)
    publication = db.get(DocumentPublication, document.id)
    if publication is not None:
        db.delete(publication)
    document.visibility = "private"
    document.share_token = None
    document.published_at = None
    db.commit()
    db.refresh(document)
    return document


def get_public_document(
    db: Session, share_token: str
) -> tuple[Document, DocumentPublication]:
    row = db.execute(
        select(Document, DocumentPublication)
        .join(
            DocumentPublication,
            DocumentPublication.document_id == Document.id,
        )
        .where(
            Document.share_token == share_token,
            Document.visibility == "public",
            Document.deleted_at.is_(None),
            DocumentPublication.owner_user_id == Document.owner_user_id,
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "share_not_found", "公开内容不存在或已取消")
    return row[0], row[1]


def publication_asset_ids(publication: DocumentPublication) -> set[int]:
    ids: set[int] = set()
    for block in publication.blocks or []:
        block_type = block.get("block_type", "")
        content = block.get("content", {})
        asset_id = block.get("asset_id")
        ids.update(
            block_asset_ids(
                block_type,
                content,
                asset_id if isinstance(asset_id, int) else None,
            )
        )
        if block_type in ("rich_text", "remark"):
            text = str(content)
            ids.update(
                int(match.group(1))
                for match in PUBLIC_ASSET_ID_RE.finditer(text)
                if match.group(1).isdigit()
            )
    return ids


def get_public_asset(
    db: Session, share_token: str, asset_id: int
) -> tuple[Document, DocumentPublication, Asset]:
    document, publication = get_public_document(db, share_token)
    if asset_id not in publication_asset_ids(publication):
        raise ApiError(404, "share_not_found", "公开图片不存在")
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.owner_user_id == document.owner_user_id,
        )
    )
    if asset is None:
        raise ApiError(404, "share_not_found", "公开图片不存在")
    path = asset_path(asset.owner_user_id, asset.storage_name)
    if not path.is_file():
        raise ApiError(404, "share_not_found", "公开图片不存在")
    return document, publication, asset


def share_url(document: Document) -> str | None:
    if not document.share_token:
        return None
    return f"{settings.public_base_path}/p/{document.share_token}"

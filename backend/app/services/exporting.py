from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Asset,
    Block,
    Chapter,
    Document,
    DocumentFavorite,
    DocumentPublication,
    RecycleEntry,
    User,
    UserProfile,
)
from app.schemas import to_iso_utc
from app.security import utcnow
from app.services.assets import asset_path
from app.services.storage import compute_storage_usage

settings = get_settings()
PUBLIC_DOCUMENT_URL = re.compile(
    r"(/public/documents/)[^/\s\"']+(/assets/)"
)


def _sanitize_export_value(value):
    if isinstance(value, str):
        return PUBLIC_DOCUMENT_URL.sub(lambda match: f"{match.group(1)}[REDACTED]{match.group(2)}", value)
    if isinstance(value, list):
        return [_sanitize_export_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _sanitize_export_value(item)
            for key, item in value.items()
        }
    return value


def _iso(value) -> str | None:
    return to_iso_utc(value)


def build_user_export(db: Session, user: User) -> Path:
    profile = db.get(UserProfile, user.id)
    chapters = db.scalars(
        select(Chapter)
        .where(Chapter.owner_user_id == user.id)
        .order_by(Chapter.sort_order, Chapter.id)
    ).all()
    documents = db.scalars(
        select(Document)
        .where(Document.owner_user_id == user.id)
        .order_by(Document.id)
    ).all()
    document_ids = [document.id for document in documents]
    blocks_by_document: dict[int, list[Block]] = {}
    if document_ids:
        for block in db.scalars(
            select(Block)
            .where(Block.document_id.in_(document_ids))
            .order_by(Block.sort_order, Block.id)
        ).all():
            blocks_by_document.setdefault(block.document_id, []).append(block)
    favorite_document_ids = set(
        db.scalars(
            select(DocumentFavorite.document_id).where(
                DocumentFavorite.user_id == user.id
            )
        ).all()
    )
    recycle_by_document = {
        entry.document_id: entry
        for entry in db.scalars(
            select(RecycleEntry).where(
                RecycleEntry.owner_user_id == user.id
            )
        ).all()
    }
    publication_by_document = {
        publication.document_id: publication
        for publication in db.scalars(
            select(DocumentPublication).where(
                DocumentPublication.owner_user_id == user.id
            )
        ).all()
    }
    assets = db.scalars(
        select(Asset)
        .where(Asset.owner_user_id == user.id)
        .order_by(Asset.id)
    ).all()
    usage = compute_storage_usage(db, user.id, user=user)

    asset_entries: list[dict] = []
    asset_files: list[tuple[Asset, Path]] = []
    for asset in assets:
        path = asset_path(user.id, asset.storage_name)
        exists = path.is_file()
        asset_entries.append(
            {
                "id": asset.id,
                "original_name": asset.original_name,
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
                "created_at": _iso(asset.created_at),
                "file": (
                    f"assets/{asset.id}{path.suffix}" if exists else None
                ),
                "missing_on_disk": not exists,
            }
        )
        if exists:
            asset_files.append((asset, path))

    document_entries = []
    for document in documents:
        publication = publication_by_document.get(document.id)
        recycle = recycle_by_document.get(document.id)
        document_entries.append(
            {
                "id": document.id,
                "kind": document.kind,
                "title": document.title,
                "summary": document.summary,
                "language": document.language,
                "visibility": document.visibility,
                "chapter_id": document.chapter_id,
                "version": document.version,
                "library_order": document.library_order,
                "chapter_order": document.chapter_order,
                "is_favorite": document.id in favorite_document_ids,
                "created_at": _iso(document.created_at),
                "updated_at": _iso(document.updated_at),
                "deleted_at": _iso(document.deleted_at),
                "recycle": (
                    {
                        "deleted_at": _iso(recycle.deleted_at),
                        "original_chapter_id": recycle.original_chapter_id,
                    }
                    if recycle is not None
                    else None
                ),
                "publication": (
                    {
                        "title": publication.title,
                        "kind": publication.kind,
                        "language": publication.language,
                        "published_at": _iso(publication.published_at),
                        "source_version": publication.source_version,
                        "author_display_name": publication.author_display_name,
                        "blocks": _sanitize_export_value(publication.blocks),
                    }
                    if publication is not None
                    else None
                ),
                "blocks": [
                    {
                        "id": block.id,
                        "block_type": block.block_type,
                        "content": block.content,
                        "asset_id": block.asset_id,
                        "sort_order": block.sort_order,
                        "created_at": _iso(block.created_at),
                        "updated_at": _iso(block.updated_at),
                    }
                    for block in blocks_by_document.get(document.id, [])
                ],
            }
        )

    payload = {
        "format": "c-notes-export-v1",
        "exported_at": _iso(utcnow()),
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": (
                profile.display_name
                if profile is not None
                else user.email.split("@", 1)[0]
            ),
            "bio": profile.bio if profile is not None else "",
            "email_verified_at": _iso(user.email_verified_at),
            "created_at": _iso(user.created_at),
        },
        "usage": {
            "quota_bytes": usage.quota_bytes,
            "used_bytes": usage.used_bytes,
            "source_bytes": usage.source_bytes,
            "note_bytes": usage.note_bytes,
            "image_bytes": usage.image_bytes,
            "recycle_bytes": usage.recycle_bytes,
        },
        "retention": {
            "recycle_days": settings.recycle_retention_days,
            "account_deletion_days": settings.account_deletion_retention_days,
        },
        "chapters": [
            {
                "id": chapter.id,
                "name": chapter.name,
                "sort_order": chapter.sort_order,
                "created_at": _iso(chapter.created_at),
                "updated_at": _iso(chapter.updated_at),
            }
            for chapter in chapters
        ],
        "documents": document_entries,
        "assets": asset_entries,
    }

    export_dir = settings.exports_path / str(user.id)
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"{uuid4().hex}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "data.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        for asset, path in asset_files:
            archive.write(
                path,
                arcname=f"assets/{asset.id}{path.suffix}",
            )
    return target

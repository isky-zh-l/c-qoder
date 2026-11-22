from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Asset,
    Block,
    Chapter,
    Document,
    DocumentPublication,
    RecycleEntry,
    UserProfile,
)
from app.security import utcnow
from app.services.content import block_asset_ids
from app.services.maintenance_lock import BACKUP_LOCK_KEY, WRITE_XACT_LOCK_SQL
from app.services.publication import publication_asset_ids

settings = get_settings()


def recycle_expires_at(deleted_at):
    return deleted_at + timedelta(days=settings.recycle_retention_days)


def purge_expired_recycle(db: Session, user_id: int) -> int:
    if not db.execute(
        text(WRITE_XACT_LOCK_SQL), {"key": BACKUP_LOCK_KEY}
    ).scalar():
        return 0
    now = utcnow()
    cutoff = now - timedelta(days=settings.recycle_retention_days)
    entries = db.scalars(
        select(RecycleEntry)
        .where(
            RecycleEntry.owner_user_id == user_id,
            RecycleEntry.deleted_at <= cutoff,
        )
        .with_for_update()
    ).all()
    if not entries:
        return 0

    document_ids = [entry.document_id for entry in entries]
    candidate_asset_ids: set[int] = set()
    for block_type, content, asset_id in db.execute(
        select(Block.block_type, Block.content, Block.asset_id).where(
            Block.document_id.in_(document_ids)
        )
    ).all():
        candidate_asset_ids.update(
            block_asset_ids(block_type, content, asset_id)
        )

    documents = db.scalars(
        select(Document).where(
            Document.owner_user_id == user_id,
            Document.id.in_(document_ids),
            Document.deleted_at.is_not(None),
        )
    ).all()
    for document in documents:
        db.delete(document)
    for entry in entries:
        db.delete(entry)
    db.flush()

    if candidate_asset_ids:
        still_used: set[int] = set()
        for block_type, content, asset_id in db.execute(
            select(Block.block_type, Block.content, Block.asset_id).where(
                Block.document_id.not_in(document_ids)
            )
        ).all():
            still_used.update(
                block_asset_ids(block_type, content, asset_id)
            )
        still_used.update(
            db.scalars(
                select(UserProfile.avatar_asset_id).where(
                    UserProfile.avatar_asset_id.in_(candidate_asset_ids)
                )
            ).all()
        )
        publications = db.scalars(
            select(DocumentPublication).where(
                DocumentPublication.owner_user_id == user_id
            )
        ).all()
        for publication in publications:
            still_used.update(publication_asset_ids(publication))
        assets = db.scalars(
            select(Asset).where(
                Asset.owner_user_id == user_id,
                Asset.id.in_(candidate_asset_ids - still_used),
            )
        ).all()
        paths = [
            settings.uploads_path / str(asset.owner_user_id) / asset.storage_name
            for asset in assets
        ]
        for asset in assets:
            db.delete(asset)
        db.commit()
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    else:
        db.commit()
    return len(entries)


def recycle_rows(db: Session, user_id: int) -> list[tuple[RecycleEntry, Document, str | None]]:
    purge_expired_recycle(db, user_id)
    rows = db.execute(
        select(RecycleEntry, Document)
        .join(Document, Document.id == RecycleEntry.document_id)
        .where(
            RecycleEntry.owner_user_id == user_id,
            Document.owner_user_id == user_id,
            Document.deleted_at.is_not(None),
        )
        .order_by(RecycleEntry.deleted_at.desc(), RecycleEntry.id.desc())
    ).all()
    chapter_names = {
        chapter.id: chapter.name
        for chapter in db.scalars(
            select(Chapter).where(Chapter.owner_user_id == user_id)
        ).all()
    }
    return [
        (entry, document, chapter_names.get(entry.original_chapter_id))
        for entry, document in rows
    ]

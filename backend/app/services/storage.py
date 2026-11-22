from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import (
    Asset,
    Block,
    Document,
    DocumentPublication,
    RecycleEntry,
    StorageReservation,
    User,
    UserProfile,
)
from app.security import utcnow
from app.services.content import block_asset_ids
from app.services.publication import publication_asset_ids

settings = get_settings()


@dataclass(frozen=True)
class StorageUsage:
    quota_bytes: int
    used_bytes: int
    reserved_bytes: int
    remaining_bytes: int
    source_bytes: int
    note_bytes: int
    image_bytes: int
    recycle_bytes: int
    publication_bytes: int
    asset_count: int
    document_count: int
    recycle_count: int

    @property
    def over_quota(self) -> bool:
        return self.used_bytes + self.reserved_bytes > self.quota_bytes


def effective_quota_bytes(user: User) -> int:
    if user.storage_quota_bytes is not None:
        return max(0, user.storage_quota_bytes)
    return max(0, settings.default_user_storage_bytes)


def lock_user_for_storage(db: Session, user_id: int) -> User:
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise ApiError(404, "not_found", "账号不存在")
    return user


def cleanup_expired_reservations(
    db: Session, user_id: int | None = None
) -> int:
    statement = delete(StorageReservation).where(
        StorageReservation.expires_at <= utcnow()
    )
    if user_id is not None:
        statement = statement.where(StorageReservation.user_id == user_id)
    result = db.execute(statement)
    return int(result.rowcount or 0)


def _json_bytes(value) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    )


def compute_storage_usage(
    db: Session,
    user_id: int,
    *,
    user: User | None = None,
) -> StorageUsage:
    if user is None:
        user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", "账号不存在")

    documents = db.scalars(
        select(Document).where(Document.owner_user_id == user_id)
    ).all()
    document_ids = [document.id for document in documents]
    blocks_by_document: dict[int, list[Block]] = {}
    if document_ids:
        for block in db.scalars(
            select(Block).where(Block.document_id.in_(document_ids))
        ).all():
            blocks_by_document.setdefault(block.document_id, []).append(block)

    active_asset_ids: set[int] = set()
    recycle_asset_ids: set[int] = set()
    active_documents = 0
    recycled_documents = 0
    source_bytes = 0
    note_bytes = 0
    recycle_text_bytes = 0

    for document in documents:
        blocks = blocks_by_document.get(document.id, [])
        size = len(document.title.encode("utf-8"))
        for block in blocks:
            size += _json_bytes(
                {"block_type": block.block_type, "content": block.content}
            )
            target = (
                recycle_asset_ids
                if document.deleted_at
                else active_asset_ids
            )
            target.update(
                block_asset_ids(
                    block.block_type,
                    block.content,
                    block.asset_id,
                )
            )
        if document.deleted_at is not None:
            recycled_documents += 1
            recycle_text_bytes += size
        else:
            active_documents += 1
            if document.kind == "source":
                source_bytes += size
            else:
                note_bytes += size

    profile = db.get(UserProfile, user_id)
    active_asset_ids.update(
        asset_id
        for asset_id in (
            profile.avatar_asset_id if profile is not None else None,
        )
        if asset_id is not None
    )
    publication_bytes = 0
    for publication in db.scalars(
        select(DocumentPublication).where(
            DocumentPublication.owner_user_id == user_id
        )
    ).all():
        active_asset_ids.update(publication_asset_ids(publication))
        publication_bytes += len(publication.title.encode("utf-8"))
        for block in publication.blocks or []:
            publication_bytes += _json_bytes(
                {
                    "block_type": block.get("block_type"),
                    "content": block.get("content", {}),
                }
            )

    asset_rows = db.execute(
        select(Asset.id, Asset.size_bytes).where(
            Asset.owner_user_id == user_id
        )
    ).all()
    image_bytes = 0
    recycle_image_bytes = 0
    for asset_id, size_bytes in asset_rows:
        if asset_id in recycle_asset_ids and asset_id not in active_asset_ids:
            recycle_image_bytes += size_bytes
        else:
            image_bytes += size_bytes

    recycle_count = (
        db.scalar(
            select(func.count())
            .select_from(RecycleEntry)
            .where(RecycleEntry.owner_user_id == user_id)
        )
        or 0
    )
    reserved_bytes = (
        db.scalar(
            select(func.coalesce(func.sum(StorageReservation.size_bytes), 0)).where(
                StorageReservation.user_id == user_id,
                StorageReservation.expires_at > utcnow(),
            )
        )
        or 0
    )

    recycle_bytes = recycle_text_bytes + recycle_image_bytes
    used_bytes = (
        source_bytes
        + note_bytes
        + image_bytes
        + recycle_bytes
        + publication_bytes
    )
    quota_bytes = effective_quota_bytes(user)
    return StorageUsage(
        quota_bytes=quota_bytes,
        used_bytes=used_bytes,
        reserved_bytes=reserved_bytes,
        remaining_bytes=max(0, quota_bytes - used_bytes - reserved_bytes),
        source_bytes=source_bytes,
        note_bytes=note_bytes,
        image_bytes=image_bytes,
        recycle_bytes=recycle_bytes,
        publication_bytes=publication_bytes,
        asset_count=len(asset_rows),
        document_count=active_documents,
        recycle_count=recycle_count,
    )


def _quota_error(usage: StorageUsage, required_bytes: int) -> ApiError:
    return ApiError(
        413,
        "storage_quota_exceeded",
        "存储空间不足，请清理回收站或删除图片后再试",
        {
            "quota_bytes": usage.quota_bytes,
            "used_bytes": usage.used_bytes,
            "reserved_bytes": usage.reserved_bytes,
            "required_bytes": required_bytes,
            "remaining_bytes": usage.remaining_bytes,
        },
    )


def reserve_storage(
    db: Session,
    user_id: int,
    size_bytes: int,
    *,
    purpose: str = "upload",
) -> StorageReservation:
    if size_bytes <= 0:
        raise ApiError(422, "validation_error", "上传文件为空")
    user = lock_user_for_storage(db, user_id)
    cleanup_expired_reservations(db, user_id)
    db.flush()
    usage = compute_storage_usage(db, user_id, user=user)
    if usage.used_bytes + usage.reserved_bytes + size_bytes > usage.quota_bytes:
        raise _quota_error(
            usage, usage.used_bytes + usage.reserved_bytes + size_bytes
        )

    now = utcnow()
    reservation = StorageReservation(
        user_id=user_id,
        size_bytes=size_bytes,
        purpose=purpose,
        created_at=now,
        expires_at=now
        + timedelta(minutes=max(1, settings.upload_reservation_minutes)),
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def release_reservation(db: Session, reservation_id: int) -> None:
    db.execute(
        delete(StorageReservation).where(
            StorageReservation.id == reservation_id
        )
    )
    db.commit()


def enforce_quota_after_change(
    db: Session,
    user: User,
    *,
    before_used_bytes: int,
) -> StorageUsage:
    db.flush()
    usage = compute_storage_usage(db, user.id, user=user)
    if usage.used_bytes + usage.reserved_bytes <= usage.quota_bytes:
        return usage
    # Admins may lower a quota below current usage. Let users shrink content,
    # but reject any change that increases their footprint.
    if usage.used_bytes <= before_used_bytes:
        return usage
    raise _quota_error(usage, usage.used_bytes)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models import Asset, Chapter, Document, RecycleEntry


def get_owned_chapter(
    db: Session, user_id: int, chapter_id: int, *, for_update: bool = False
) -> Chapter:
    statement = select(Chapter).where(
        Chapter.id == chapter_id, Chapter.owner_user_id == user_id
    )
    if for_update:
        statement = statement.with_for_update()
    chapter = db.execute(statement).scalar_one_or_none()
    if chapter is None:
        raise not_found("章节不存在")
    return chapter


def get_owned_document(
    db: Session,
    user_id: int,
    document_id: int,
    *,
    include_deleted: bool = False,
    for_update: bool = False,
) -> Document:
    statement = select(Document).where(
        Document.id == document_id, Document.owner_user_id == user_id
    )
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    if for_update:
        statement = statement.with_for_update()
    document = db.execute(statement).scalar_one_or_none()
    if document is None:
        raise not_found("文档不存在")
    return document


def get_owned_asset(db: Session, user_id: int, asset_id: int) -> Asset:
    asset = db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.owner_user_id == user_id)
    ).scalar_one_or_none()
    if asset is None:
        raise not_found("图片不存在")
    return asset


def get_owned_recycle(
    db: Session, user_id: int, recycle_id: int, *, for_update: bool = False
) -> RecycleEntry:
    statement = select(RecycleEntry).where(
        RecycleEntry.id == recycle_id,
        RecycleEntry.owner_user_id == user_id,
    )
    if for_update:
        statement = statement.with_for_update()
    entry = db.execute(statement).scalar_one_or_none()
    if entry is None:
        raise not_found("回收记录不存在")
    return entry

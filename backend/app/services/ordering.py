from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentFavorite


def next_library_order(db: Session, user_id: int) -> int:
    current = db.scalar(
        select(func.max(Document.library_order)).where(
            Document.owner_user_id == user_id,
            Document.deleted_at.is_(None),
        )
    )
    return (current if current is not None else -1) + 1


def next_chapter_order(db: Session, user_id: int, chapter_id: int) -> int:
    current = db.scalar(
        select(func.max(Document.chapter_order)).where(
            Document.owner_user_id == user_id,
            Document.chapter_id == chapter_id,
            Document.deleted_at.is_(None),
        )
    )
    return (current if current is not None else -1) + 1


def next_favorite_order(db: Session, user_id: int) -> int:
    current = db.scalar(
        select(func.max(DocumentFavorite.favorite_order)).where(
            DocumentFavorite.user_id == user_id
        )
    )
    return (current if current is not None else -1) + 1


def compact_library(db: Session, user_id: int) -> None:
    documents = db.scalars(
        select(Document)
        .where(
            Document.owner_user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.library_order, Document.id)
    ).all()
    for index, document in enumerate(documents):
        document.library_order = index


def compact_chapter(db: Session, user_id: int, chapter_id: int) -> None:
    documents = db.scalars(
        select(Document)
        .where(
            Document.owner_user_id == user_id,
            Document.chapter_id == chapter_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.chapter_order, Document.id)
    ).all()
    for index, document in enumerate(documents):
        document.chapter_order = index


def compact_favorites(db: Session, user_id: int) -> None:
    rows = db.execute(
        select(DocumentFavorite)
        .join(Document, Document.id == DocumentFavorite.document_id)
        .where(
            DocumentFavorite.user_id == user_id,
            Document.owner_user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(DocumentFavorite.favorite_order, DocumentFavorite.document_id)
    ).scalars().all()
    for index, favorite in enumerate(rows):
        favorite.favorite_order = index

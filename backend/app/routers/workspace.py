from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import (
    Asset,
    Chapter,
    Document,
    DocumentFavorite,
    RecycleEntry,
    User,
)
from app.schemas import (
    ChapterOut,
    WorkspaceOut,
    WorkspaceStorageOut,
)
from app.services.recycle import purge_expired_recycle
from app.services.users import user_out

router = APIRouter()
settings = get_settings()


@router.get("/workspace", response_model=WorkspaceOut)
def get_workspace(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    purge_expired_recycle(db, user.id)

    chapter_rows = db.execute(
        select(Chapter, func.count(Document.id))
        .outerjoin(
            Document,
            and_(
                Document.chapter_id == Chapter.id,
                Document.deleted_at.is_(None),
            ),
        )
        .where(Chapter.owner_user_id == user.id)
        .group_by(Chapter.id)
        .order_by(Chapter.sort_order, Chapter.id)
    ).all()

    library_count = db.scalar(
        select(func.count()).select_from(Document).where(
            Document.owner_user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    favorite_count = db.scalar(
        select(func.count())
        .select_from(DocumentFavorite)
        .join(Document, Document.id == DocumentFavorite.document_id)
        .where(
            DocumentFavorite.user_id == user.id,
            Document.owner_user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    recycle_count = db.scalar(
        select(func.count()).select_from(RecycleEntry).where(
            RecycleEntry.owner_user_id == user.id
        )
    )
    asset_count, total_bytes = db.execute(
        select(
            func.count(Asset.id),
            func.coalesce(func.sum(Asset.size_bytes), 0),
        ).where(Asset.owner_user_id == user.id)
    ).one()

    return WorkspaceOut(
        user=user_out(db, user),
        chapters=[
            ChapterOut(
                id=chapter.id,
                name=chapter.name,
                sort_order=chapter.sort_order,
                document_count=count,
            )
            for chapter, count in chapter_rows
        ],
        favorite_count=favorite_count or 0,
        library_count=library_count or 0,
        recycle_count=recycle_count or 0,
        storage=WorkspaceStorageOut(
            asset_count=asset_count or 0,
            total_bytes=total_bytes or 0,
        ),
        recycle_retention_days=settings.recycle_retention_days,
    )

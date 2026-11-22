from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Chapter, Document, User
from app.schemas import ChapterCreate, ChapterOrderIn, ChapterOut, ChapterUpdate
from app.services.access import get_owned_chapter

router = APIRouter()


@router.get("/chapters", response_model=list[ChapterOut])
def list_chapters(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    statement = (
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
    )
    return [
        ChapterOut(
            id=chapter.id,
            name=chapter.name,
            sort_order=chapter.sort_order,
            document_count=count,
        )
        for chapter, count in db.execute(statement).all()
    ]


@router.post("/chapters", response_model=ChapterOut, status_code=201)
def create_chapter(
    payload: ChapterCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_order = db.scalar(
        select(func.max(Chapter.sort_order)).where(
            Chapter.owner_user_id == user.id
        )
    )
    chapter = Chapter(
        owner_user_id=user.id,
        name=payload.name,
        sort_order=(max_order if max_order is not None else -1) + 1,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return ChapterOut(
        id=chapter.id,
        name=chapter.name,
        sort_order=chapter.sort_order,
        document_count=0,
    )


@router.patch("/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: int,
    payload: ChapterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = get_owned_chapter(db, user.id, chapter_id, for_update=True)
    chapter.name = payload.name
    count = db.scalar(
        select(func.count(Document.id)).where(
            Document.chapter_id == chapter.id,
            Document.deleted_at.is_(None),
        )
    )
    db.commit()
    db.refresh(chapter)
    return ChapterOut(
        id=chapter.id,
        name=chapter.name,
        sort_order=chapter.sort_order,
        document_count=count or 0,
    )


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(
    chapter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = get_owned_chapter(db, user.id, chapter_id, for_update=True)
    documents = db.scalars(
        select(Document).where(
            Document.owner_user_id == user.id,
            Document.chapter_id == chapter.id,
        )
    ).all()
    for document in documents:
        document.chapter_id = None
        document.chapter_order = 0
    db.delete(chapter)
    db.commit()


@router.put("/chapters/order", status_code=204)
def reorder_chapters(
    payload: ChapterOrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapters = db.scalars(
        select(Chapter)
        .where(Chapter.owner_user_id == user.id)
        .with_for_update()
    ).all()
    by_id = {chapter.id: chapter for chapter in chapters}
    submitted = payload.chapter_ids
    if len(set(submitted)) != len(submitted) or set(submitted) != set(by_id):
        raise ApiError(
            409,
            "order_conflict",
            "章节顺序列表与当前账号范围不一致",
            {"current_chapter_ids": sorted(by_id)},
        )
    for index, chapter_id in enumerate(submitted):
        by_id[chapter_id].sort_order = index
    db.commit()

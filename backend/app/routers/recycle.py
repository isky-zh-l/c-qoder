import math

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import DocumentDetailOut, RecycleOut, RestoreIn
from app.security import utcnow
from app.services.documents import detail_out, restore_document
from app.services.recycle import recycle_expires_at, recycle_rows

router = APIRouter()


@router.get("/recycle", response_model=list[RecycleOut])
def get_recycle(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    now = utcnow()
    return [
        RecycleOut(
            id=entry.id,
            document_id=document.id,
            title=document.title,
            kind=document.kind,
            original_chapter_id=entry.original_chapter_id,
            original_chapter_name=chapter_name,
            deleted_at=entry.deleted_at,
            expires_at=recycle_expires_at(entry.deleted_at),
            days_remaining=max(
                0,
                math.ceil(
                    (recycle_expires_at(entry.deleted_at) - now).total_seconds()
                    / 86400
                ),
            ),
        )
        for entry, document, chapter_name in recycle_rows(db, user.id)
    ]


@router.post("/recycle/{recycle_id}/restore", response_model=DocumentDetailOut)
def restore_recycled_document(
    recycle_id: int,
    payload: RestoreIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = restore_document(
        db,
        user.id,
        recycle_id,
        title=payload.title,
        title_provided="title" in payload.model_fields_set,
    )
    return detail_out(db, user.id, document)

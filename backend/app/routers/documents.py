from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Document, DocumentFavorite, User
from app.schemas import (
    DocumentCreate,
    DocumentDetailOut,
    DocumentOrderIn,
    DocumentPatch,
    DocumentSaveIn,
    DocumentSummaryOut,
    FavoriteCountOut,
    PublicationOut,
    VisibilityUpdate,
)
from app.services.access import get_owned_chapter, get_owned_document
from app.services.documents import (
    create_document,
    detail_out,
    favorite_document,
    parse_if_match,
    recycle_document,
    save_document,
    summary_out,
    unfavorite_document,
)
from app.config import get_settings
from app.services.importing import import_document
from app.services.publication import (
    publish_document,
    share_url,
    unpublish_document,
)
from app.services.source import source_code, source_filename

router = APIRouter()
settings = get_settings()


def _validate_order(submitted: list[int], current: set[int]) -> None:
    if len(set(submitted)) != len(submitted) or set(submitted) != current:
        raise ApiError(
            409,
            "order_conflict",
            "排序列表与当前账号范围不一致",
            {"current_document_ids": sorted(current)},
        )


@router.get("/documents", response_model=list[DocumentSummaryOut])
def list_documents(
    scope: Literal["library", "chapter", "favorites"] = Query(default="library"),
    chapter_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = select(Document).where(
        Document.owner_user_id == user.id,
        Document.deleted_at.is_(None),
    )
    favorite_ids = set(
        db.scalars(
            select(DocumentFavorite.document_id).where(
                DocumentFavorite.user_id == user.id
            )
        ).all()
    )

    if scope == "chapter":
        if chapter_id is None:
            raise ApiError(422, "validation_error", "章节范围必须提供 chapter_id")
        get_owned_chapter(db, user.id, chapter_id)
        statement = (
            base.where(Document.chapter_id == chapter_id)
            .order_by(Document.chapter_order, Document.id)
        )
    elif scope == "favorites":
        statement = (
            base.join(
                DocumentFavorite,
                DocumentFavorite.document_id == Document.id,
            )
            .where(DocumentFavorite.user_id == user.id)
            .order_by(DocumentFavorite.favorite_order, Document.id)
        )
    else:
        statement = base.order_by(Document.library_order, Document.id)

    documents = db.scalars(statement).all()
    return [
        summary_out(
            db,
            user.id,
            document,
            is_favorite=document.id in favorite_ids,
        )
        for document in documents
    ]


@router.get("/favorites/count", response_model=FavoriteCountOut)
def favorite_count(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    count = db.scalar(
        select(func.count())
        .select_from(DocumentFavorite)
        .join(Document, Document.id == DocumentFavorite.document_id)
        .where(
            DocumentFavorite.user_id == user.id,
            Document.owner_user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    return FavoriteCountOut(count=count or 0)


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, user.id, document_id)
    return detail_out(db, user.id, document)


@router.get("/documents/{document_id}/download")
def download_source_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, user.id, document_id)
    if document.kind != "source":
        raise ApiError(404, "not_found", "源码文档不存在")
    filename = source_filename(document)
    fallback = f"source.{document.language or 'txt'}"
    return Response(
        content=source_code(db, document),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{fallback}\"; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/documents", response_model=DocumentDetailOut, status_code=201)
def create_new_document(
    payload: DocumentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = create_document(
        db,
        user.id,
        kind=payload.kind,
        title=payload.title,
        chapter_id=payload.chapter_id,
        language=payload.language,
    )
    return detail_out(db, user.id, document)


@router.post(
    "/documents/import", response_model=DocumentDetailOut, status_code=201
)
async def import_new_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    chapter_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contents = await file.read(settings.max_file_bytes + 1)
    if len(contents) > settings.max_file_bytes:
        raise ApiError(
            413,
            "payload_too_large",
            f"导入文件不能超过 {settings.max_file_bytes // (1024 * 1024)} MB",
        )
    document = import_document(
        db,
        user.id,
        filename=file.filename or "",
        contents=contents,
        title=title,
        chapter_id=chapter_id,
    )
    return detail_out(db, user.id, document)


@router.patch("/documents/{document_id}", response_model=DocumentDetailOut)
def patch_document(
    document_id: int,
    payload: DocumentPatch,
    if_match: str | None = Header(default=None, alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expected_version = parse_if_match(if_match)
    provided = payload.model_fields_set
    document = save_document(
        db,
        user.id,
        document_id,
        expected_version=expected_version,
        title=payload.title,
        title_provided="title" in provided,
        chapter_id=payload.chapter_id,
        chapter_provided="chapter_id" in provided,
    )
    return detail_out(db, user.id, document)


@router.put("/documents/{document_id}/blocks", response_model=DocumentDetailOut)
def save_document_blocks(
    document_id: int,
    payload: DocumentSaveIn,
    if_match: str | None = Header(default=None, alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expected_version = parse_if_match(if_match)
    provided = payload.model_fields_set
    document = save_document(
        db,
        user.id,
        document_id,
        expected_version=expected_version,
        title=payload.title,
        title_provided="title" in provided,
        chapter_id=payload.chapter_id,
        chapter_provided="chapter_id" in provided,
        blocks=payload.blocks,
        blocks_provided=True,
    )
    return detail_out(db, user.id, document)


@router.put(
    "/documents/{document_id}/visibility",
    response_model=PublicationOut,
)
def update_document_visibility(
    document_id: int,
    payload: VisibilityUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    if payload.visibility == "public":
        document, publication = publish_document(db, user.id, document_id)
        return PublicationOut(
            visibility="public",
            share_token=document.share_token,
            share_url=share_url(document),
            published_at=publication.published_at,
            published_version=publication.source_version,
        )

    unpublish_document(db, user.id, document_id)
    response.headers["Clear-Site-Data"] = '"cache"'
    return PublicationOut(
        visibility="private",
        share_token=None,
        share_url=None,
        published_at=None,
        published_version=None,
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recycle_document(db, user.id, document_id)


@router.put("/documents/{document_id}/favorite", status_code=204)
def add_favorite(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite_document(db, user.id, document_id)


@router.delete("/documents/{document_id}/favorite", status_code=204)
def remove_favorite(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unfavorite_document(db, user.id, document_id)


@router.put("/orders/library", status_code=204)
def reorder_library(
    payload: DocumentOrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documents = db.scalars(
        select(Document)
        .where(
            Document.owner_user_id == user.id,
            Document.deleted_at.is_(None),
        )
        .with_for_update()
    ).all()
    by_id = {document.id: document for document in documents}
    _validate_order(payload.document_ids, set(by_id))
    for index, document_id in enumerate(payload.document_ids):
        by_id[document_id].library_order = index
    db.commit()


@router.put("/orders/chapters/{chapter_id}", status_code=204)
def reorder_chapter_documents(
    chapter_id: int,
    payload: DocumentOrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_chapter(db, user.id, chapter_id)
    documents = db.scalars(
        select(Document)
        .where(
            Document.owner_user_id == user.id,
            Document.chapter_id == chapter_id,
            Document.deleted_at.is_(None),
        )
        .with_for_update()
    ).all()
    by_id = {document.id: document for document in documents}
    _validate_order(payload.document_ids, set(by_id))
    for index, document_id in enumerate(payload.document_ids):
        by_id[document_id].chapter_order = index
    db.commit()


@router.put("/orders/favorites", status_code=204)
def reorder_favorites(
    payload: DocumentOrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorites = db.scalars(
        select(DocumentFavorite)
        .join(Document, Document.id == DocumentFavorite.document_id)
        .where(
            DocumentFavorite.user_id == user.id,
            Document.owner_user_id == user.id,
            Document.deleted_at.is_(None),
        )
        .with_for_update()
    ).all()
    by_id = {favorite.document_id: favorite for favorite in favorites}
    _validate_order(payload.document_ids, set(by_id))
    for index, document_id in enumerate(payload.document_ids):
        by_id[document_id].favorite_order = index
    db.commit()

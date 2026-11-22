import re
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    Block,
    Chapter,
    Document,
    DocumentFavorite,
    DocumentPublication,
    RecycleEntry,
)
from app.schemas import BlockOut, DocumentDetailOut, DocumentSummaryOut
from app.security import clean_title, title_key, utcnow
from app.services.access import (
    get_owned_asset,
    get_owned_chapter,
    get_owned_document,
    get_owned_recycle,
)
from app.services.content import (
    rich_content_asset_ids,
    rich_content_plain_text,
    validate_code_content,
    validate_formula_content,
    validate_image_content,
    validate_rich_text_content,
)
from app.services.ordering import (
    compact_chapter,
    compact_favorites,
    compact_library,
    next_chapter_order,
    next_favorite_order,
    next_library_order,
)
from app.services.publication import share_url as public_share_url
from app.services.recycle import purge_expired_recycle, recycle_expires_at
from app.services.storage import (
    compute_storage_usage,
    enforce_quota_after_change,
    lock_user_for_storage,
)

NOTE_BLOCK_TYPES = {"rich_text", "code", "image", "formula"}
SOURCE_BLOCK_TYPES = {"code", "remark", "result", "image"}
IF_MATCH_RE = re.compile(r'^(?:W/)?"?(\d+)"?$')


def parse_if_match(value: str | None) -> int:
    if value is None or not value.strip():
        raise ApiError(
            428,
            "precondition_required",
            "保存前必须提供 If-Match 版本",
        )
    match = IF_MATCH_RE.match(value.strip())
    if not match:
        raise ApiError(428, "precondition_required", "If-Match 版本格式不正确")
    return int(match.group(1))


def ensure_title_available(
    db: Session, user_id: int, key: str, *, exclude_document_id: int | None = None
) -> None:
    statement = select(Document.id).where(
        Document.owner_user_id == user_id,
        Document.title_key == key,
        Document.deleted_at.is_(None),
    )
    if exclude_document_id is not None:
        statement = statement.where(Document.id != exclude_document_id)
    existing = db.scalar(statement)
    if existing is not None:
        raise ApiError(
            409,
            "document_name_conflict",
            "同一账号已存在同名文档",
        )


def _validate_block_content(
    block_type: str,
    content: dict[str, Any],
    *,
    kind: str,
    document_language: str | None,
) -> None:
    if block_type in ("rich_text", "remark"):
        validate_rich_text_content(
            content,
            kind="note" if block_type == "remark" else kind,
        )
        return
    if block_type == "code":
        validate_code_content(content)
        if (
            kind == "source"
            and document_language is not None
            and content.get("language") != document_language
        ):
            raise ApiError(
                422,
                "validation_error",
                "源码模块语言必须与文档语言一致",
            )
        return
    if block_type == "result":
        if not isinstance(content.get("text"), str):
            raise ApiError(422, "validation_error", "运行结果模块缺少 text")
        return
    if block_type == "formula":
        validate_formula_content(content)
        return
    if block_type == "image":
        validate_image_content(content)
        return


def prepare_block_payloads(
    db: Session,
    user_id: int,
    kind: str,
    blocks: list[Any],
    *,
    document_language: str | None = None,
) -> list[dict[str, Any]]:
    allowed = NOTE_BLOCK_TYPES if kind == "note" else SOURCE_BLOCK_TYPES
    result: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if block.block_type not in allowed:
            raise ApiError(
                422,
                "validation_error",
                f"{kind} 文档不支持模块类型 {block.block_type}",
            )
        _validate_block_content(
            block.block_type,
            block.content,
            kind=kind,
            document_language=document_language,
        )

        if block.block_type == "image":
            if block.asset_id is None:
                raise ApiError(422, "validation_error", "图片模块必须引用资产")
            get_owned_asset(db, user_id, block.asset_id)
        elif block.asset_id is not None:
            raise ApiError(422, "validation_error", "只有图片模块可以引用资产")

        if block.block_type in ("rich_text", "remark"):
            for asset_id in rich_content_asset_ids(block.content):
                get_owned_asset(db, user_id, asset_id)

        result.append(
            {
                "id": block.id,
                "block_type": block.block_type,
                "content": block.content,
                "asset_id": block.asset_id,
                "sort_order": index,
            }
        )
    return result


def build_blocks(payloads: list[dict[str, Any]]) -> list[Block]:
    return [
        Block(
            block_type=payload["block_type"],
            content=payload["content"],
            asset_id=payload["asset_id"],
            sort_order=payload["sort_order"],
        )
        for payload in payloads
    ]


def _extract_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_extract_text(item))
        return parts
    if isinstance(value, dict):
        parts: list[str] = []
        if isinstance(value.get("text"), str):
            parts.append(value["text"])
        if "content" in value:
            parts.extend(_extract_text(value["content"]))
        return parts
    return []


def derive_summary(payloads: list[dict[str, Any]]) -> str:
    for block in payloads:
        if block["block_type"] in ("rich_text", "remark"):
            content = block["content"]
            text = rich_content_plain_text(content)
            if not text:
                text = " ".join(_extract_text(content))
            text = " ".join(text.split())
            if text:
                return text[:120]
    return ""


def _chapter_name(db: Session, user_id: int, document: Document) -> str | None:
    if document.chapter_id is None:
        return None
    chapter = db.scalar(
        select(Chapter).where(
            Chapter.id == document.chapter_id,
            Chapter.owner_user_id == user_id,
        )
    )
    return chapter.name if chapter is not None else None


def _is_favorite(db: Session, user_id: int, document_id: int) -> bool:
    return (
        db.scalar(
            select(DocumentFavorite.document_id).where(
                DocumentFavorite.user_id == user_id,
                DocumentFavorite.document_id == document_id,
            )
        )
        is not None
    )


def summary_out(
    db: Session,
    user_id: int,
    document: Document,
    *,
    is_favorite: bool | None = None,
) -> DocumentSummaryOut:
    if is_favorite is None:
        is_favorite = _is_favorite(db, user_id, document.id)
    return DocumentSummaryOut(
        id=document.id,
        kind=document.kind,
        title=document.title,
        summary=document.summary,
        chapter_id=document.chapter_id,
        chapter_name=_chapter_name(db, user_id, document),
        language=document.language,
        visibility=document.visibility,
        is_favorite=is_favorite,
        version=document.version,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def detail_out(db: Session, user_id: int, document: Document) -> DocumentDetailOut:
    blocks = db.scalars(
        select(Block)
        .where(Block.document_id == document.id)
        .order_by(Block.sort_order, Block.id)
    ).all()
    summary = summary_out(db, user_id, document)
    publication = db.get(DocumentPublication, document.id)
    share_token = (
        document.share_token
        if publication is not None and document.visibility == "public"
        else None
    )
    return DocumentDetailOut(
        **summary.model_dump(),
        share_token=share_token,
        share_url=public_share_url(document) if share_token else None,
        published_at=publication.published_at if publication else None,
        published_version=(
            publication.source_version if publication else None
        ),
        blocks=[
            BlockOut(
                id=block.id,
                block_type=block.block_type,
                content=block.content,
                asset_id=block.asset_id,
                sort_order=block.sort_order,
            )
            for block in blocks
        ],
    )


def create_document(
    db: Session,
    user_id: int,
    *,
    kind: str,
    title: str,
    chapter_id: int | None,
    language: str | None,
    blocks: list[Any] | None = None,
) -> Document:
    user = lock_user_for_storage(db, user_id)
    before_usage = compute_storage_usage(db, user_id, user=user)
    cleaned_title = clean_title(title)
    key = title_key(cleaned_title)
    ensure_title_available(db, user_id, key)

    chapter = None
    if chapter_id is not None:
        chapter = get_owned_chapter(db, user_id, chapter_id)
    payloads = prepare_block_payloads(
        db,
        user_id,
        kind,
        blocks or [],
        document_language=language,
    )
    if any(payload["id"] is not None for payload in payloads):
        raise ApiError(422, "validation_error", "新文档不能提交已有模块 ID")
    new_blocks = build_blocks(payloads)

    document = Document(
        owner_user_id=user_id,
        chapter_id=chapter.id if chapter else None,
        kind=kind,
        title=cleaned_title,
        title_key=key,
        summary=derive_summary(payloads),
        language=language,
        visibility="private",
        version=1,
        library_order=next_library_order(db, user_id),
        chapter_order=next_chapter_order(db, user_id, chapter.id) if chapter else 0,
        deleted_at=None,
    )
    db.add(document)
    try:
        db.flush()
        for block in new_blocks:
            block.document_id = document.id
            db.add(block)
        enforce_quota_after_change(
            db,
            user,
            before_used_bytes=before_usage.used_bytes,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "document_name_conflict", "同一账号已存在同名文档")
    except Exception:
        db.rollback()
        raise
    db.refresh(document)
    return document


def save_document(
    db: Session,
    user_id: int,
    document_id: int,
    *,
    expected_version: int,
    title: str | None = None,
    title_provided: bool = False,
    chapter_id: int | None = None,
    chapter_provided: bool = False,
    blocks: list[Any] | None = None,
    blocks_provided: bool = False,
) -> Document:
    user = lock_user_for_storage(db, user_id)
    before_usage = compute_storage_usage(db, user_id, user=user)
    document = get_owned_document(db, user_id, document_id, for_update=True)
    if document.version != expected_version:
        raise ApiError(
            409,
            "version_conflict",
            "文档已在其他设备更新",
            {
                "current_version": document.version,
                "current_updated_at": document.updated_at.isoformat(),
            },
        )

    new_title = document.title
    new_key = document.title_key
    if title_provided:
        new_title = clean_title(title or "")
        if not new_title:
            raise ApiError(422, "validation_error", "标题不能为空")
        new_key = title_key(new_title)
        ensure_title_available(
            db, user_id, new_key, exclude_document_id=document.id
        )

    target_chapter: Chapter | None = None
    target_chapter_id = document.chapter_id
    target_chapter_order = document.chapter_order
    if chapter_provided:
        if chapter_id is not None:
            target_chapter = get_owned_chapter(db, user_id, chapter_id)
            target_chapter_id = target_chapter.id
            if target_chapter_id != document.chapter_id:
                target_chapter_order = next_chapter_order(
                    db, user_id, target_chapter.id
                )
        else:
            target_chapter_id = None
            target_chapter_order = 0

    payloads: list[dict[str, Any]] | None = None
    existing_blocks: dict[int, Block] = {}
    removed_blocks: list[Block] = []
    if blocks_provided:
        payloads = prepare_block_payloads(
            db,
            user_id,
            document.kind,
            blocks or [],
            document_language=document.language,
        )
        existing = db.scalars(
            select(Block)
            .where(Block.document_id == document.id)
            .with_for_update()
        ).all()
        existing_blocks = {block.id: block for block in existing}
        submitted_ids: set[int] = set()
        for payload in payloads:
            block_id = payload["id"]
            if block_id is None:
                continue
            if block_id in submitted_ids:
                raise ApiError(422, "validation_error", "模块 ID 重复")
            submitted_ids.add(block_id)
            if block_id not in existing_blocks:
                raise ApiError(404, "not_found", "模块不存在或不属于当前文档")
        removed_blocks = [
            block for block_id, block in existing_blocks.items()
            if block_id not in submitted_ids
        ]

    if title_provided:
        document.title = new_title
        document.title_key = new_key

    if chapter_provided:
        document.chapter_id = target_chapter_id
        document.chapter_order = target_chapter_order

    if blocks_provided and payloads is not None:
        for block in removed_blocks:
            db.delete(block)
        for payload in payloads:
            block_id = payload["id"]
            if block_id is None:
                db.add(
                    Block(
                        document_id=document.id,
                        block_type=payload["block_type"],
                        content=payload["content"],
                        asset_id=payload["asset_id"],
                        sort_order=payload["sort_order"],
                    )
                )
            else:
                block = existing_blocks[block_id]
                block.block_type = payload["block_type"]
                block.content = payload["content"]
                block.asset_id = payload["asset_id"]
                block.sort_order = payload["sort_order"]
        document.summary = derive_summary(payloads)

    document.version += 1
    document.updated_at = utcnow()

    try:
        enforce_quota_after_change(
            db,
            user,
            before_used_bytes=before_usage.used_bytes,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "document_name_conflict", "同一账号已存在同名文档")
    except Exception:
        db.rollback()
        raise
    db.refresh(document)
    return document


def recycle_document(db: Session, user_id: int, document_id: int) -> RecycleEntry:
    document = get_owned_document(db, user_id, document_id, for_update=True)
    now = utcnow()
    publication = db.get(DocumentPublication, document.id)
    if publication is not None:
        db.delete(publication)
    document.visibility = "private"
    document.share_token = None
    document.published_at = None
    document.deleted_at = now
    document.library_order = 0
    document.chapter_order = 0
    entry = RecycleEntry(
        owner_user_id=user_id,
        document_id=document.id,
        original_chapter_id=document.chapter_id,
        deleted_at=now,
    )
    db.add(entry)
    db.execute(
        delete(DocumentFavorite).where(
            DocumentFavorite.user_id == user_id,
            DocumentFavorite.document_id == document.id,
        )
    )
    db.flush()
    compact_library(db, user_id)
    if document.chapter_id is not None:
        compact_chapter(db, user_id, document.chapter_id)
    compact_favorites(db, user_id)
    db.commit()
    db.refresh(entry)
    return entry


def restore_document(
    db: Session,
    user_id: int,
    recycle_id: int,
    *,
    title: str | None = None,
    title_provided: bool = False,
) -> Document:
    entry = get_owned_recycle(db, user_id, recycle_id, for_update=True)
    if recycle_expires_at(entry.deleted_at) <= utcnow():
        purge_expired_recycle(db, user_id)
        raise ApiError(404, "not_found", "回收记录已超过保留时间")
    document = get_owned_document(
        db, user_id, entry.document_id, include_deleted=True, for_update=True
    )

    new_title = document.title
    new_key = document.title_key
    if title_provided:
        new_title = clean_title(title or "")
        if not new_title:
            raise ApiError(422, "validation_error", "标题不能为空")
        new_key = title_key(new_title)
    ensure_title_available(db, user_id, new_key, exclude_document_id=document.id)

    target_chapter: Chapter | None = None
    if entry.original_chapter_id is not None:
        target_chapter = db.scalar(
            select(Chapter).where(
                Chapter.id == entry.original_chapter_id,
                Chapter.owner_user_id == user_id,
            )
        )

    document.deleted_at = None
    document.title = new_title
    document.title_key = new_key
    document.chapter_id = target_chapter.id if target_chapter else None
    document.library_order = next_library_order(db, user_id)
    document.chapter_order = (
        next_chapter_order(db, user_id, target_chapter.id) if target_chapter else 0
    )
    document.version += 1
    document.updated_at = utcnow()
    db.delete(entry)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "document_name_conflict", "同一账号已存在同名文档")
    db.refresh(document)
    return document


def favorite_document(db: Session, user_id: int, document_id: int) -> None:
    get_owned_document(db, user_id, document_id)
    existing = db.get(DocumentFavorite, (user_id, document_id))
    if existing is None:
        db.add(
            DocumentFavorite(
                user_id=user_id,
                document_id=document_id,
                favorite_order=next_favorite_order(db, user_id),
            )
        )
        db.commit()


def unfavorite_document(db: Session, user_id: int, document_id: int) -> None:
    get_owned_document(db, user_id, document_id)
    existing = db.get(DocumentFavorite, (user_id, document_id))
    if existing is not None:
        db.delete(existing)
        db.flush()
        compact_favorites(db, user_id)
        db.commit()

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.errors import ApiError
from app.models import (
    AdminAuditLog,
    AuthSession,
    Document,
    DocumentPublication,
    User,
    UserProfile,
)
from app.security import utcnow
from app.services.settings import (
    registration_enabled,
    set_registration_enabled,
)
from app.services.storage import StorageUsage, compute_storage_usage


def add_audit(
    db: Session,
    *,
    admin_user_id: int | None,
    action: str,
    target_user_id: int | None = None,
    target_document_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AdminAuditLog:
    entry = AdminAuditLog(
        admin_user_id=admin_user_id,
        action=action,
        target_user_id=target_user_id,
        target_document_id=target_document_id,
        details=details or {},
    )
    db.add(entry)
    return entry


def update_registration_setting(
    db: Session, admin: User, enabled: bool
) -> bool:
    previous = registration_enabled(db)
    set_registration_enabled(db, enabled)
    add_audit(
        db,
        admin_user_id=admin.id,
        action="registration.set",
        details={"before": previous, "after": enabled},
    )
    db.commit()
    return enabled


def update_user_enabled(
    db: Session, admin: User, user_id: int, enabled: bool
) -> User:
    if user_id == admin.id and not enabled:
        raise ApiError(409, "self_action_not_allowed", "不能暂停自己的管理员账号")
    target = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise ApiError(404, "not_found", "用户不存在")
    if enabled and target.deletion_requested_at is not None:
        raise ApiError(409, "deletion_pending", "注销处理中的账号不能恢复")
    if target.is_enabled == enabled:
        return target

    previous = target.is_enabled
    target.is_enabled = enabled
    if not enabled:
        now = utcnow()
        db.execute(
            delete(DocumentPublication).where(
                DocumentPublication.owner_user_id == target.id
            )
        )
        db.execute(
            update(Document)
            .where(Document.owner_user_id == target.id)
            .values(
                visibility="private",
                share_token=None,
                published_at=None,
            )
        )
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == target.id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
    add_audit(
        db,
        admin_user_id=admin.id,
        action="user.status",
        target_user_id=target.id,
        details={"before": previous, "after": enabled},
    )
    db.commit()
    db.refresh(target)
    return target


def update_user_quota(
    db: Session, admin: User, user_id: int, quota_bytes: int | None
) -> User:
    target = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if target is None:
        raise ApiError(404, "not_found", "用户不存在")
    previous = target.storage_quota_bytes
    target.storage_quota_bytes = quota_bytes
    add_audit(
        db,
        admin_user_id=admin.id,
        action="user.quota",
        target_user_id=target.id,
        details={"before": previous, "after": quota_bytes},
    )
    db.commit()
    db.refresh(target)
    return target


def list_users(
    db: Session,
    *,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[User, UserProfile | None, StorageUsage]], int]:
    base = select(User, UserProfile).outerjoin(
        UserProfile, UserProfile.user_id == User.id
    )
    count_statement = select(func.count()).select_from(User)
    if query:
        pattern = f"%{query.strip().lower()}%"
        base = base.where(
            or_(
                func.lower(User.email).like(pattern),
                func.lower(func.coalesce(UserProfile.display_name, "")).like(
                    pattern
                ),
            )
        )
        count_statement = count_statement.outerjoin(
            UserProfile, UserProfile.user_id == User.id
        ).where(
            or_(
                func.lower(User.email).like(pattern),
                func.lower(func.coalesce(UserProfile.display_name, "")).like(
                    pattern
                ),
            )
        )
    total = db.scalar(count_statement) or 0
    rows = db.execute(
        base.order_by(User.id).limit(limit).offset(offset)
    ).all()
    return [
        (user, profile, compute_storage_usage(db, user.id, user=user))
        for user, profile in rows
    ], total


def list_public_documents(
    db: Session, *, limit: int = 100
) -> list[tuple[DocumentPublication, Document, User]]:
    return db.execute(
        select(DocumentPublication, Document, User)
        .join(Document, Document.id == DocumentPublication.document_id)
        .join(User, User.id == DocumentPublication.owner_user_id)
        .where(
            Document.visibility == "public",
            Document.deleted_at.is_(None),
        )
        .order_by(DocumentPublication.published_at.desc())
        .limit(limit)
    ).all()


def unpublish_public_document(
    db: Session, admin: User, document_id: int
) -> Document:
    document = db.execute(
        select(Document).where(Document.id == document_id).with_for_update()
    ).scalar_one_or_none()
    if document is None:
        raise ApiError(404, "not_found", "公开文档不存在")
    publication = db.get(DocumentPublication, document.id)
    if (
        publication is None
        or document.visibility != "public"
        or document.deleted_at is not None
    ):
        raise ApiError(404, "not_found", "公开文档不存在")
    title = publication.title
    owner_user_id = document.owner_user_id
    db.delete(publication)
    document.visibility = "private"
    document.share_token = None
    document.published_at = None
    add_audit(
        db,
        admin_user_id=admin.id,
        action="publication.unpublish",
        target_user_id=owner_user_id,
        target_document_id=document.id,
        details={"title": title},
    )
    db.commit()
    db.refresh(document)
    return document


def list_audit_entries(
    db: Session, *, limit: int = 100
) -> list[
    tuple[
        AdminAuditLog,
        str | None,
        str | None,
        str | None,
    ]
]:
    admin_user = aliased(User)
    target_user = aliased(User)
    rows = db.execute(
        select(
            AdminAuditLog,
            admin_user.email,
            target_user.email,
            Document.title,
        )
        .outerjoin(admin_user, admin_user.id == AdminAuditLog.admin_user_id)
        .outerjoin(target_user, target_user.id == AdminAuditLog.target_user_id)
        .outerjoin(Document, Document.id == AdminAuditLog.target_document_id)
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .limit(limit)
    ).all()
    return [(entry, admin_email, target_email, title) for entry, admin_email, target_email, title in rows]

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.models import User, UserProfile
from app.schemas import (
    AdminAuditListOut,
    AdminAuditOut,
    AdminPublicDocumentOut,
    AdminPublicListOut,
    AdminQuotaIn,
    AdminRegistrationIn,
    AdminSettingsOut,
    AdminUserListOut,
    AdminUserOut,
    AdminUserStatusIn,
)
from app.services import admin as admin_service
from app.services.publication import share_url
from app.services.settings import registration_enabled
from app.services.storage import StorageUsage, compute_storage_usage

router = APIRouter()


def _user_out(
    db: Session,
    user: User,
    profile: UserProfile | None,
    usage: StorageUsage,
) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=(
            profile.display_name
            if profile is not None
            else user.email.split("@", 1)[0]
        ),
        is_enabled=user.is_enabled,
        is_admin=user.is_admin,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        storage_quota_bytes=user.storage_quota_bytes,
        effective_quota_bytes=usage.quota_bytes,
        used_bytes=usage.used_bytes,
        reserved_bytes=usage.reserved_bytes,
        document_count=usage.document_count,
        recycle_count=usage.recycle_count,
        deletion_requested_at=user.deletion_requested_at,
        purge_after=user.purge_after,
    )


@router.get("/admin/settings", response_model=AdminSettingsOut)
def get_settings(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return AdminSettingsOut(registration_enabled=registration_enabled(db))


@router.put("/admin/settings/registration", response_model=AdminSettingsOut)
def update_registration(
    payload: AdminRegistrationIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    enabled = admin_service.update_registration_setting(db, admin, payload.enabled)
    return AdminSettingsOut(registration_enabled=enabled)


@router.get("/admin/users", response_model=AdminUserListOut)
def get_users(
    query: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows, total = admin_service.list_users(
        db, query=query, limit=limit, offset=offset
    )
    return AdminUserListOut(
        users=[
            _user_out(db, user, profile, usage)
            for user, profile, usage in rows
        ],
        total=total,
    )


@router.put("/admin/users/{user_id}/status", response_model=AdminUserOut)
def update_user_status(
    user_id: int,
    payload: AdminUserStatusIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = admin_service.update_user_enabled(db, admin, user_id, payload.enabled)
    profile = db.get(UserProfile, user.id)
    usage = compute_storage_usage(db, user.id, user=user)
    return _user_out(db, user, profile, usage)


@router.put("/admin/users/{user_id}/quota", response_model=AdminUserOut)
def update_user_quota(
    user_id: int,
    payload: AdminQuotaIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = admin_service.update_user_quota(
        db, admin, user_id, payload.quota_bytes
    )
    profile = db.get(UserProfile, user.id)
    usage = compute_storage_usage(db, user.id, user=user)
    return _user_out(db, user, profile, usage)


@router.get("/admin/publications", response_model=AdminPublicListOut)
def get_publications(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = admin_service.list_public_documents(db)
    return AdminPublicListOut(
        documents=[
            AdminPublicDocumentOut(
                document_id=document.id,
                title=publication.title,
                owner_user_id=owner.id,
                owner_email=owner.email,
                author_display_name=publication.author_display_name,
                published_at=publication.published_at,
                source_version=publication.source_version,
                share_url=share_url(document),
            )
            for publication, document, owner in rows
        ]
    )


@router.delete("/admin/publications/{document_id}", status_code=204)
def unpublish_publication(
    document_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    admin_service.unpublish_public_document(db, admin, document_id)


@router.get("/admin/audit", response_model=AdminAuditListOut)
def get_audit(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = admin_service.list_audit_entries(db)
    return AdminAuditListOut(
        entries=[
            AdminAuditOut(
                id=entry.id,
                action=entry.action,
                admin_user_id=entry.admin_user_id,
                admin_email=admin_email,
                target_user_id=entry.target_user_id,
                target_user_email=target_email,
                target_document_id=entry.target_document_id,
                target_document_title=document_title,
                details=entry.details,
                created_at=entry.created_at,
            )
            for entry, admin_email, target_email, document_title in rows
        ]
    )

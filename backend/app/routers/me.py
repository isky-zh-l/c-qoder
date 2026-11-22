from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import User, UserProfile
from app.schemas import (
    AccountDeleteIn,
    AccountDeletionOut,
    ProfileUpdate,
    StorageLimitsOut,
    StorageUsageOut,
    UserOut,
)
from app.security import verify_password
from app.services.access import get_owned_asset
from app.services.account import request_account_deletion
from app.services.exporting import build_user_export
from app.services.storage import compute_storage_usage
from app.services.users import user_out

router = APIRouter()
settings = get_settings()


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(db, user)


@router.patch("/me/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(
            user_id=user.id,
            display_name=user.email.split("@", 1)[0],
            bio="",
        )
        db.add(profile)
        db.flush()

    provided = payload.model_fields_set
    if "display_name" in provided and payload.display_name is not None:
        profile.display_name = payload.display_name
    if "bio" in provided and payload.bio is not None:
        profile.bio = payload.bio
    if "avatar_asset_id" in provided:
        if payload.avatar_asset_id is not None:
            get_owned_asset(db, user.id, payload.avatar_asset_id)
        profile.avatar_asset_id = payload.avatar_asset_id

    db.commit()
    db.refresh(profile)
    return user_out(db, user)


@router.get("/me/usage", response_model=StorageUsageOut)
def get_storage_usage(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    usage = compute_storage_usage(db, user.id, user=user)
    return StorageUsageOut(
        quota_bytes=usage.quota_bytes,
        used_bytes=usage.used_bytes,
        reserved_bytes=usage.reserved_bytes,
        remaining_bytes=usage.remaining_bytes,
        source_bytes=usage.source_bytes,
        note_bytes=usage.note_bytes,
        image_bytes=usage.image_bytes,
        recycle_bytes=usage.recycle_bytes,
        publication_bytes=usage.publication_bytes,
        asset_count=usage.asset_count,
        document_count=usage.document_count,
        recycle_count=usage.recycle_count,
        over_quota=usage.over_quota,
        limits=StorageLimitsOut(
            max_file_bytes=settings.max_file_bytes,
            max_image_bytes=settings.max_image_bytes,
            image_max_dimension=settings.image_max_dimension,
        ),
        recycle_retention_days=settings.recycle_retention_days,
        account_deletion_retention_days=settings.account_deletion_retention_days,
    )


@router.get("/me/export")
def export_my_data(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    target = build_user_export(db, user)
    return FileResponse(
        target,
        media_type="application/zip",
        filename=f"c-notes-export-{user.id}.zip",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(target.unlink, missing_ok=True),
    )


@router.post("/me/delete", response_model=AccountDeletionOut)
def delete_my_account(
    payload: AccountDeleteIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.confirmation.strip() != "注销账号":
        raise ApiError(
            422,
            "validation_error",
            "请输入“注销账号”以确认",
        )
    if not verify_password(user.password_hash, payload.current_password):
        raise ApiError(400, "invalid_credentials", "当前密码不正确")
    deleted = request_account_deletion(db, user.id)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path=settings.session_cookie_path,
    )
    return AccountDeletionOut(
        message="注销申请已提交，登录和公开链接已停用",
        purge_after=deleted.purge_after,
        retention_days=settings.account_deletion_retention_days,
    )

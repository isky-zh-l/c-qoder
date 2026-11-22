import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import Asset, StorageReservation, User
from app.schemas import AssetOut
from app.services.access import get_owned_asset
from app.services.assets import asset_path
from app.services.images import inspect_image, safe_original_name
from app.services.storage import release_reservation, reserve_storage

router = APIRouter()
settings = get_settings()
CHUNK_SIZE = 1024 * 1024


@router.post("/assets", response_model=AssetOut, status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings.storage_tmp_path.mkdir(parents=True, exist_ok=True)
    temp_path = settings.storage_tmp_path / f"{uuid4().hex}.upload"
    reservation = None
    committed = False
    target: Path | None = None
    try:
        total = 0
        with temp_path.open("wb") as handle:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.max_image_bytes:
                    raise ApiError(
                        413,
                        "payload_too_large",
                        f"图片不能超过 {settings.max_image_bytes // (1024 * 1024)} MB",
                    )
                handle.write(chunk)

        image = inspect_image(temp_path, total)
        reservation = reserve_storage(
            db,
            user.id,
            total,
            purpose="image",
        )

        storage_name = f"{uuid4().hex}{image.extension}"
        target = asset_path(user.id, storage_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, target)

        asset = Asset(
            owner_user_id=user.id,
            storage_name=storage_name,
            original_name=safe_original_name(file.filename, image.extension),
            mime_type=image.mime_type,
            size_bytes=total,
        )
        try:
            db.add(asset)
            db.execute(
                delete(StorageReservation).where(
                    StorageReservation.id == reservation.id
                )
            )
            db.commit()
            committed = True
        except Exception:
            db.rollback()
            target.unlink(missing_ok=True)
            raise
        db.refresh(asset)
        return AssetOut(
            id=asset.id,
            original_name=asset.original_name,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
        )
    except OSError:
        if target is not None:
            target.unlink(missing_ok=True)
        raise ApiError(
            500,
            "storage_write_failed",
            "图片写入失败，请稍后重试",
        )
    finally:
        temp_path.unlink(missing_ok=True)
        if reservation is not None and not committed:
            release_reservation(db, reservation.id)


@router.get("/assets/{asset_id}/file")
def get_asset_file(
    asset_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = get_owned_asset(db, user.id, asset_id)
    path = asset_path(user.id, asset.storage_name)
    if not path.is_file():
        raise ApiError(404, "not_found", "图片文件不存在")
    return FileResponse(
        path,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/assets/{asset_id}/download")
def download_asset(
    asset_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = get_owned_asset(db, user.id, asset_id)
    path = asset_path(user.id, asset.storage_name)
    if not path.is_file():
        raise ApiError(404, "not_found", "图片文件不存在")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=asset.original_name,
        headers={"Cache-Control": "private, no-store"},
    )

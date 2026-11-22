from uuid import uuid4

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import SiteSetting
from app.schemas import (
    HealthOut,
    PublicAuthorOut,
    PublicBlockOut,
    PublicDocumentOut,
    PublicSiteOut,
)
from app.services.assets import asset_path
from app.services.publication import get_public_asset, get_public_document
from app.services.settings import registration_enabled

router = APIRouter()
settings = get_settings()


def _check_uploads() -> bool:
    try:
        settings.uploads_path.mkdir(parents=True, exist_ok=True)
        probe = settings.uploads_path / f".health-{uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_ok = False
    uploads_ok = _check_uploads()
    status = "ok" if database_ok and uploads_ok else "degraded"
    payload = HealthOut(
        status=status,
        database="ok" if database_ok else "error",
        uploads="ok" if uploads_ok else "error",
        version=settings.app_version,
    )
    if status != "ok":
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload


@router.get("/public/site", response_model=PublicSiteOut)
def public_site(db: Session = Depends(get_db)):
    setting = db.get(SiteSetting, "site_name")
    return PublicSiteOut(
        site_title=setting.setting_value if setting else settings.site_title,
        registration_enabled=registration_enabled(db),
    )


@router.get(
    "/public/documents/{share_token}",
    response_model=PublicDocumentOut,
)
def public_document(
    share_token: str,
    response: Response,
    db: Session = Depends(get_db),
):
    _document, publication = get_public_document(db, share_token)
    response.headers["Cache-Control"] = (
        "no-store, max-age=0, must-revalidate"
    )
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return PublicDocumentOut(
        title=publication.title,
        kind=publication.kind,
        language=publication.language,
        author=PublicAuthorOut(
            display_name=publication.author_display_name
        ),
        published_at=publication.published_at,
        blocks=[
            PublicBlockOut(
                block_type=block["block_type"],
                content=block["content"],
                asset_id=block.get("asset_id"),
                sort_order=block["sort_order"],
            )
            for block in publication.blocks
        ],
    )


@router.get(
    "/public/documents/{share_token}/assets/{asset_id}"
)
def public_asset(
    share_token: str,
    asset_id: int,
    db: Session = Depends(get_db),
):
    document, _publication, asset = get_public_asset(
        db, share_token, asset_id
    )
    path = asset_path(document.owner_user_id, asset.storage_name)
    return FileResponse(
        path,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "no-store, max-age=0, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Robots-Tag": "noindex, nofollow",
            "X-Content-Type-Options": "nosniff",
        },
    )

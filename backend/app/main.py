import logging
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.db import engine
from app.csrf import require_csrf
from app.errors import ApiError
from app.logging_utils import install_logging_redaction
from app.routers import (
    admin,
    assets,
    auth,
    chapters,
    documents,
    me,
    public,
    recycle,
    workspace,
)
from app.services.maintenance_lock import BACKUP_LOCK_KEY, WRITE_LOCK_SQL, WRITE_UNLOCK_SQL
from app.services.rate_limit import consume_rate_limit

logger = logging.getLogger("c_notes")
settings = get_settings()
api_base = settings.api_base_path
install_logging_redaction()

app = FastAPI(
    title=settings.site_title,
    version=settings.app_version,
    docs_url=f"{api_base}/docs",
    redoc_url=None,
    openapi_url=f"{api_base}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-CSRF-Token", "If-Match"],
)

app.include_router(public.router, prefix=api_base, tags=["public"])
app.include_router(auth.router, prefix=api_base, tags=["auth"])
app.include_router(
    me.router, prefix=api_base, tags=["me"], dependencies=[Depends(require_csrf)]
)
app.include_router(
    workspace.router,
    prefix=api_base,
    tags=["workspace"],
    dependencies=[Depends(require_csrf)],
)
app.include_router(
    chapters.router,
    prefix=api_base,
    tags=["chapters"],
    dependencies=[Depends(require_csrf)],
)
app.include_router(
    documents.router,
    prefix=api_base,
    tags=["documents"],
    dependencies=[Depends(require_csrf)],
)
app.include_router(
    assets.router,
    prefix=api_base,
    tags=["assets"],
    dependencies=[Depends(require_csrf)],
)
app.include_router(
    recycle.router,
    prefix=api_base,
    tags=["recycle"],
    dependencies=[Depends(require_csrf)],
)
app.include_router(
    admin.router,
    prefix=api_base,
    tags=["admin"],
    dependencies=[Depends(require_csrf)],
)


@app.middleware("http")
async def maintenance_write_guard(request: Request, call_next):
    path = request.url.path
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and path.startswith(f"{api_base}/")
    ):
        with engine.connect() as connection:
            locked = connection.execute(
                text(WRITE_LOCK_SQL), {"key": BACKUP_LOCK_KEY}
            ).scalar()
            if not locked:
                return JSONResponse(
                    status_code=503,
                    headers={"Retry-After": "5"},
                    content={
                        "error": {
                            "code": "maintenance_in_progress",
                            "message": "系统正在做一致性备份，请稍后重试",
                            "details": {},
                        }
                    },
                )
            try:
                return await call_next(request)
            finally:
                connection.execute(
                    text(WRITE_UNLOCK_SQL), {"key": BACKUP_LOCK_KEY}
                )
    return await call_next(request)


@app.middleware("http")
async def request_rate_limit(request: Request, call_next):
    path = request.url.path
    if (
        request.method not in {"OPTIONS"}
        and path.startswith(f"{api_base}/")
        and path != f"{api_base}/health"
    ):
        client = request.client.host if request.client is not None else "unknown"
        try:
            consume_rate_limit(
                "request",
                client,
                settings.rate_limit_request_per_minute,
                60,
            )
        except ApiError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                headers=exc.headers,
                content={
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                },
            )
    return await call_next(request)


@app.middleware("http")
async def private_api_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (
        path.startswith(f"{api_base}/")
        and not path.startswith(f"{api_base}/public/")
    ):
        response.headers.setdefault("Cache-Control", "private, no-store")
        response.headers.setdefault("Pragma", "no-cache")
    return response


@app.middleware("http")
async def public_share_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith(f"{api_base}/public/documents/"):
        response.headers["Cache-Control"] = (
            "no-store, max-age=0, must-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["X-Content-Type-Options"] = "nosniff"
    elif path.startswith(f"{settings.public_base_path}/p/"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )
    return response


@app.middleware("http")
async def guard_write_origin(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin is None:
            referer = request.headers.get("referer")
            if referer:
                parsed = urlparse(referer)
                if parsed.scheme and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin is not None and origin not in settings.allowed_origins:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "origin_not_allowed",
                        "message": "请求来源不被允许",
                        "details": {},
                    }
                },
            )
    return await call_next(request)

ERROR_CODES = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    428: "precondition_required",
    429: "rate_limited",
}


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    code = ERROR_CODES.get(exc.status_code, "http_error")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": {},
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
):
    fields = []
    for error in exc.errors():
        location = [
            str(part)
            for part in error.get("loc", ())
            if part not in ("body", "query", "path")
        ]
        if location:
            fields.append(".".join(location))
    field_text = "、".join(dict.fromkeys(fields))
    message = "请求参数不合法" + (f"：{field_text}" if field_text else "")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": message,
                "details": {},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception):
    logger.exception("Unhandled application error")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "服务器内部错误",
                "details": {},
            }
        },
    )


@app.get("/", include_in_schema=False)
def redirect_root_to_public_base():
    return RedirectResponse(
        url=f"{settings.public_base_path}/",
        status_code=308,
    )


frontend_dist = settings.frontend_dist_path
if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount(
            f"{settings.public_base_path}/assets",
            StaticFiles(directory=assets_dir),
            name="assets",
        )

    @app.get(settings.public_base_path, include_in_schema=False)
    def redirect_to_base():
        return RedirectResponse(url=f"{settings.public_base_path}/")

    @app.get(f"{settings.public_base_path}/", include_in_schema=False)
    def serve_index():
        return FileResponse(
            frontend_dist / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get(f"{settings.public_base_path}/{{full_path:path}}", include_in_schema=False)
    def serve_frontend(full_path: str):
        api_relative = settings.api_prefix.strip("/")
        if full_path == api_relative or full_path.startswith(f"{api_relative}/"):
            raise HTTPException(status_code=404, detail="接口不存在")

        candidate = (frontend_dist / full_path).resolve()
        try:
            candidate.relative_to(frontend_dist)
        except ValueError:
            raise HTTPException(status_code=404, detail="资源不存在")

        if candidate.is_file():
            return FileResponse(
                candidate, headers={"Cache-Control": "public, max-age=3600"}
            )

        return FileResponse(
            frontend_dist / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

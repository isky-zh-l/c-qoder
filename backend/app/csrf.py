import hmac

from fastapi import Depends, Request

from app.auth import get_current_auth
from app.config import get_settings
from app.errors import ApiError
from app.security import hash_token

settings = get_settings()
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def require_csrf(
    request: Request,
    auth=Depends(get_current_auth),
) -> None:
    if request.method in SAFE_METHODS:
        return

    token = request.headers.get(settings.csrf_header_name)
    expected = auth[0].csrf_token_hash
    if (
        not token
        or not expected
        or not hmac.compare_digest(hash_token(token), expected)
    ):
        raise ApiError(403, "csrf_failed", "CSRF 校验失败，请刷新页面后重试")

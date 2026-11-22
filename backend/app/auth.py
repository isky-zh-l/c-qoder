from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError, unauthenticated
from app.models import AuthSession, User
from app.security import hash_token

settings = get_settings()


def read_session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def resolve_session(
    db: Session, request: Request
) -> tuple[AuthSession, User] | None:
    token = read_session_token(request)
    if not token:
        return None

    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(
            AuthSession.token_hash == hash_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
            User.is_enabled.is_(True),
            User.email_verified_at.is_not(None),
        )
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def get_optional_auth(
    request: Request, db: Session = Depends(get_db)
) -> tuple[AuthSession, User] | None:
    return resolve_session(db, request)


def get_current_auth(
    request: Request, db: Session = Depends(get_db)
) -> tuple[AuthSession, User]:
    auth = resolve_session(db, request)
    if auth is None:
        raise unauthenticated()
    return auth


def get_current_user(
    auth: tuple[AuthSession, User] = Depends(get_current_auth),
) -> User:
    return auth[1]


def get_optional_user(
    auth: tuple[AuthSession, User] | None = Depends(get_optional_auth),
) -> User | None:
    return auth[1] if auth else None


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ApiError(403, "forbidden", "需要管理员权限")
    return user

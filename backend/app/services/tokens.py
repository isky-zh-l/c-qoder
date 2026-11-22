from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import AuthToken
from app.security import generate_token, hash_token, utcnow


def issue_token(
    db: Session, *, user_id: int, purpose: str, ttl_hours: int
) -> str:
    now = utcnow()
    db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    raw_token = generate_token()
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(hours=ttl_hours),
        )
    )
    return raw_token


def require_valid_token(db: Session, raw_token: str, purpose: str) -> AuthToken:
    token = db.execute(
        select(AuthToken)
        .where(
            AuthToken.token_hash == hash_token(raw_token),
            AuthToken.purpose == purpose,
            AuthToken.consumed_at.is_(None),
            AuthToken.expires_at > utcnow(),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if token is None:
        raise ApiError(400, "invalid_token", "链接无效、已过期或已使用")
    return token

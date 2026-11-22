import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db import SessionLocal
from app.errors import ApiError
from app.models import RateLimit


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(
        epoch - (epoch % window_seconds), tz=timezone.utc
    )


def consume_rate_limit(scope: str, subject: str, limit: int, window_seconds: int) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled or limit <= 0:
        return

    now = datetime.now(timezone.utc)
    window_start = _window_start(now, window_seconds)
    subject_hash = hashlib.sha256(subject.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        statement = (
            insert(RateLimit)
            .values(
                scope=scope,
                subject_hash=subject_hash,
                window_start=window_start,
                count=1,
            )
            .on_conflict_do_update(
                index_elements=[
                    RateLimit.scope,
                    RateLimit.subject_hash,
                    RateLimit.window_start,
                ],
                set_={"count": RateLimit.count + 1},
            )
            .returning(RateLimit.count)
        )
        count = db.execute(statement).scalar_one()
        db.commit()
    finally:
        db.close()

    if count > limit:
        retry_after = max(
            1,
            int(
                (
                    window_start
                    + timedelta(seconds=window_seconds)
                    - now
                ).total_seconds()
            )
            + 1,
        )
        raise ApiError(
            429,
            "rate_limited",
            "请求过于频繁，请稍后再试",
            {"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

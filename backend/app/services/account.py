from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import AuthSession, Document, DocumentPublication, User
from app.security import utcnow
from app.services.storage import lock_user_for_storage

settings = get_settings()


def request_account_deletion(
    db: Session, user_id: int
) -> User:
    user = lock_user_for_storage(db, user_id)
    if user.deletion_requested_at is not None:
        raise ApiError(409, "deletion_pending", "注销申请已在处理中")
    if user.is_admin:
        enabled_admins = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.is_admin.is_(True),
                    User.is_enabled.is_(True),
                    User.deletion_requested_at.is_(None),
                )
            )
            or 0
        )
        if enabled_admins <= 1:
            raise ApiError(
                409,
                "last_admin",
                "不能注销最后一个可用管理员账号",
            )

    now = utcnow()
    purge_after = now + timedelta(
        days=max(1, settings.account_deletion_retention_days)
    )
    db.execute(
        delete(DocumentPublication).where(
            DocumentPublication.owner_user_id == user.id
        )
    )
    db.execute(
        update(Document)
        .where(Document.owner_user_id == user.id)
        .values(
            visibility="private",
            share_token=None,
            published_at=None,
        )
    )
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    user.is_enabled = False
    user.deletion_requested_at = now
    user.purge_after = purge_after
    db.commit()
    db.refresh(user)
    return user

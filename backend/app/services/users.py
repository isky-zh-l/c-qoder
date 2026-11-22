from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserProfile
from app.schemas import UserOut
from app.security import hash_password, normalize_email, utcnow


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
    verified: bool = True,
    enabled: bool = True,
    is_admin: bool = False,
) -> User:
    normalized_email = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise ValueError("email already exists")

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        email_verified_at=utcnow() if verified else None,
        is_enabled=enabled,
        is_admin=is_admin,
    )
    db.add(user)
    db.flush()

    profile = UserProfile(
        user_id=user.id,
        display_name=(display_name or normalized_email.split("@", 1)[0]).strip(),
        bio="",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user


def user_out(db: Session, user: User) -> UserOut:
    profile = db.get(UserProfile, user.id)
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=(
            profile.display_name
            if profile is not None
            else user.email.split("@", 1)[0]
        ),
        bio=profile.bio if profile is not None else "",
        avatar_asset_id=profile.avatar_asset_id if profile is not None else None,
        email_verified_at=user.email_verified_at,
        is_enabled=user.is_enabled,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )

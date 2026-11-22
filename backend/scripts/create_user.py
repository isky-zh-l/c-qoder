import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.security import normalize_email
from app.services.users import create_user
from app.services.workspace import initialize_user_workspace


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local account")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--unverified", action="store_true")
    parser.add_argument("--disabled", action="store_true")
    args = parser.parse_args()

    if len(args.password) < 10:
        parser.error("password must be at least 10 characters")

    db = SessionLocal()
    try:
        existing = db.scalar(
            select(User).where(User.email == normalize_email(args.email))
        )
        if existing is not None:
            parser.error("email already exists")
        user = create_user(
            db,
            email=args.email,
            password=args.password,
            display_name=args.display_name,
            verified=not args.unverified,
            enabled=not args.disabled,
        )
        initialize_user_workspace(db, user.id)
        db.commit()
        print(f"created user {user.id} <{user.email}>")
    finally:
        db.close()


if __name__ == "__main__":
    main()

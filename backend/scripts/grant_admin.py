import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AdminAuditLog, User
from app.security import normalize_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant or revoke admin access")
    parser.add_argument("email")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="remove admin access instead of granting it",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.scalar(
            select(User).where(User.email == normalize_email(args.email))
        )
        if user is None:
            parser.error("user does not exist")
        previous = user.is_admin
        user.is_admin = not args.revoke
        if previous != user.is_admin:
            db.add(
                AdminAuditLog(
                    admin_user_id=None,
                    action="admin.revoke" if args.revoke else "admin.grant",
                    target_user_id=user.id,
                    details={"email": user.email, "before": previous, "after": user.is_admin},
                )
            )
        db.commit()
        action = "revoked" if args.revoke else "granted"
        print(f"admin {action}: user={user.id} email={user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

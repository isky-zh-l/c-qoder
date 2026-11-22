import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.services.maintenance import (
    cleanup_expired_uploads,
    purge_due_accounts,
    scan_orphan_files,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Storage and account maintenance")
    parser.add_argument(
        "command",
        choices=["report", "run"],
        nargs="?",
        default="report",
    )
    parser.add_argument("--temp-hours", type=float, default=1.0)
    parser.add_argument("--export-hours", type=float, default=24.0)
    parser.add_argument("--orphan-grace-hours", type=float, default=None)
    parser.add_argument("--delete-orphans", action="store_true")
    parser.add_argument("--purge-accounts", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.command == "report":
            orphans = scan_orphan_files(
                db,
                grace_hours=args.orphan_grace_hours,
            )
            print(
                json.dumps(
                    {
                        "orphan_files": len(orphans.files),
                        "orphan_bytes": orphans.total_bytes,
                        "missing_files": len(orphans.missing),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        report = cleanup_expired_uploads(
            db,
            older_than_hours=args.temp_hours,
            exports_older_than_hours=args.export_hours,
            orphan_grace_hours=args.orphan_grace_hours,
            delete_orphans=args.delete_orphans,
        )
        if args.purge_accounts:
            report.purged_accounts = purge_due_accounts(db)
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()

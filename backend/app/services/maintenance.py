from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, Document, StorageReservation, User
from app.security import utcnow
from app.services.assets import asset_path
from app.services.maintenance_lock import (
    BACKUP_LOCK_KEY,
    WRITE_LOCK_SQL,
    WRITE_UNLOCK_SQL,
    WRITE_XACT_LOCK_SQL,
)
from app.services.storage import cleanup_expired_reservations

settings = get_settings()


@dataclass
class OrphanReport:
    files: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(path.stat().st_size for path in self.files if path.is_file())


@dataclass
class MaintenanceReport:
    expired_reservations: int = 0
    temp_files: int = 0
    export_files: int = 0
    orphan_files: int = 0
    orphan_bytes: int = 0
    missing_files: int = 0
    purged_accounts: int = 0
    deleted_files: int = 0


def cleanup_temp_files(
    *,
    older_than_hours: float = 1.0,
    root: Path | None = None,
) -> int:
    root = root or settings.storage_tmp_path
    if not root.is_dir():
        return 0
    cutoff = utcnow().timestamp() - older_than_hours * 3600
    removed = 0
    for path in root.iterdir():
        if not path.is_file() or path.stat().st_mtime > cutoff:
            continue
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def cleanup_export_files(
    *,
    older_than_hours: float = 24.0,
    root: Path | None = None,
) -> int:
    root = root or settings.exports_path
    if not root.is_dir():
        return 0
    cutoff = utcnow().timestamp() - older_than_hours * 3600
    removed = 0
    for path in root.rglob("*.zip"):
        if not path.is_file() or path.stat().st_mtime > cutoff:
            continue
        path.unlink(missing_ok=True)
        removed += 1
    for directory in sorted(root.rglob("*"), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass
    return removed


def scan_orphan_files(
    db: Session,
    *,
    grace_hours: float | None = None,
    root: Path | None = None,
) -> OrphanReport:
    root = root or settings.uploads_path
    if not root.is_dir():
        return OrphanReport()
    cutoff = utcnow().timestamp() - (
        settings.storage_orphan_grace_hours
        if grace_hours is None
        else grace_hours
    ) * 3600
    known: set[tuple[int, str]] = {
        (int(owner_id), str(storage_name))
        for owner_id, storage_name in db.execute(
            select(Asset.owner_user_id, Asset.storage_name)
        ).all()
    }
    report = OrphanReport()
    for user_dir in root.iterdir():
        if not user_dir.is_dir() or not user_dir.name.isdigit():
            continue
        owner_id = int(user_dir.name)
        for path in user_dir.iterdir():
            if not path.is_file():
                continue
            if (owner_id, path.name) not in known and path.stat().st_mtime <= cutoff:
                report.files.append(path)
    for asset in db.scalars(select(Asset)).all():
        path = asset_path(asset.owner_user_id, asset.storage_name)
        if not path.is_file():
            report.missing.append(path)
    return report


def delete_orphan_files(
    report: OrphanReport, *, root: Path | None = None
) -> int:
    root = root or settings.uploads_path
    root_resolved = root.resolve()
    removed = 0
    for path in report.files:
        resolved = path.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            continue
        resolved.unlink(missing_ok=True)
        removed += 1
    return removed


def cleanup_expired_uploads(
    db: Session,
    *,
    older_than_hours: float = 1.0,
    exports_older_than_hours: float = 24.0,
    orphan_grace_hours: float | None = None,
    delete_orphans: bool = False,
) -> MaintenanceReport:
    if not db.execute(
        text(WRITE_LOCK_SQL), {"key": BACKUP_LOCK_KEY}
    ).scalar():
        return MaintenanceReport()
    try:
        report = MaintenanceReport()
        report.expired_reservations = cleanup_expired_reservations(db)
        db.commit()
        report.temp_files = cleanup_temp_files(older_than_hours=older_than_hours)
        report.export_files = cleanup_export_files(
            older_than_hours=exports_older_than_hours
        )
        orphans = scan_orphan_files(
            db,
            grace_hours=orphan_grace_hours,
        )
        report.orphan_files = len(orphans.files)
        report.orphan_bytes = orphans.total_bytes
        report.missing_files = len(orphans.missing)
        if delete_orphans:
            report.deleted_files = delete_orphan_files(orphans)
        return report
    finally:
        db.execute(text(WRITE_UNLOCK_SQL), {"key": BACKUP_LOCK_KEY})
        db.commit()


def purge_due_accounts(db: Session) -> int:
    if not db.execute(
        text(WRITE_XACT_LOCK_SQL), {"key": BACKUP_LOCK_KEY}
    ).scalar():
        return 0
    now = utcnow()
    users = db.scalars(
        select(User)
        .where(
            User.purge_after.is_not(None),
            User.purge_after <= now,
            User.deletion_requested_at.is_not(None),
        )
        .with_for_update(skip_locked=True)
    ).all()
    if not users:
        return 0
    user_ids = [user.id for user in users]
    asset_rows = db.execute(
        select(Asset.owner_user_id, Asset.storage_name).where(
            Asset.owner_user_id.in_(user_ids)
        )
    ).all()
    paths = [
        asset_path(owner_id, storage_name)
        for owner_id, storage_name in asset_rows
    ]
    # Delete documents first so image blocks disappear before assets set
    # blocks.asset_id to NULL (image blocks require a non-null asset).
    db.execute(delete(Document).where(Document.owner_user_id.in_(user_ids)))
    db.flush()
    db.execute(delete(Asset).where(Asset.owner_user_id.in_(user_ids)))
    db.execute(delete(User).where(User.id.in_(user_ids)))
    db.commit()
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    for user_id in user_ids:
        user_dir = settings.uploads_path / str(user_id)
        try:
            user_dir.rmdir()
        except OSError:
            pass
        export_dir = settings.exports_path / str(user_id)
        try:
            for path in export_dir.glob("*"):
                path.unlink(missing_ok=True)
            export_dir.rmdir()
        except OSError:
            pass
    return len(user_ids)

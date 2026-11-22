import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

import psycopg
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.engine import make_url

from app.config import get_settings
from app.security import utcnow
from app.services.maintenance_lock import BACKUP_LOCK_KEY

settings = get_settings()


def _tool(name: str) -> str:
    env_name = "PG_DUMP" if name == "pg_dump" else "PG_RESTORE"
    configured = os.environ.get(env_name)
    if configured:
        return configured
    found = shutil.which(name)
    if found:
        return found
    try:
        import pgserver

        candidate = (
            Path(pgserver.__file__).resolve().parent
            / "pginstall"
            / "bin"
            / (f"{name}.exe" if os.name == "nt" else name)
        )
        if candidate.is_file():
            return str(candidate)
    except Exception:
        pass
    raise RuntimeError(f"{name} not found; set {env_name}")


def _database_tool_target(
    database_url: str,
) -> tuple[str, dict[str, str]]:
    url = make_url(database_url).set(drivername="postgresql")
    password = url.password
    safe_url = url._replace(password=None) if password else url
    env = os.environ.copy()
    if password:
        # Keep the password out of argv, logs and manifest; pg tools read it
        # from the environment.
        env["PGPASSWORD"] = password
    return str(safe_url), env


def _database_url_for_connection(database_url: str) -> str:
    # Only used in-process to open the advisory-lock connection; never printed.
    return (
        make_url(database_url)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )


def _redacted_database(database_url: str) -> str:
    url = make_url(database_url)
    host = url.host or "local"
    port = f":{url.port}" if url.port else ""
    database = url.database or "?"
    return f"{url.username or '?'}@{host}{port}/{database}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hash(root: Path) -> tuple[int, int, str]:
    if not root.exists():
        return 0, 0, hashlib.sha256(b"").hexdigest()
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        file_count += 1
        total_bytes += path.stat().st_size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_file(path).encode("ascii"))
    return file_count, total_bytes, digest.hexdigest()


def _run(command: list[str], env: dict[str, str] | None = None) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "PostgreSQL tool failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )


def create_backup(backup_dir: Path, uploads_dir: Path) -> Path:
    if backup_dir.exists() and any(backup_dir.iterdir()):
        raise RuntimeError(f"backup directory is not empty: {backup_dir}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    database_target, database_env = _database_tool_target(
        settings.database_url
    )
    lock_connection = psycopg.connect(
        _database_url_for_connection(settings.database_url),
        autocommit=True,
    )
    try:
        # Exclusive lock: app writes use a shared lock; maintenance cleanup also
        # checks the same lock. Wait for in-flight writes to finish, then block
        # new writes until the database dump and uploads copy are complete.
        lock_connection.execute(
            "SELECT pg_advisory_lock(%s)", (BACKUP_LOCK_KEY,)
        )
        asset_rows = lock_connection.execute(
            "SELECT owner_user_id, storage_name FROM assets ORDER BY id"
        ).fetchall()
        asset_files = [
            f"{int(owner_id)}/{storage_name}"
            for owner_id, storage_name in asset_rows
        ]

        dump_path = backup_dir / "database.dump"
        _run(
            [
                _tool("pg_dump"),
                "--dbname",
                database_target,
                "--format=custom",
                "--file",
                str(dump_path),
            ],
            env=database_env,
        )
        uploads_target = backup_dir / "uploads"
        if uploads_dir.is_dir():
            shutil.copytree(uploads_dir, uploads_target)
        else:
            uploads_target.mkdir(parents=True, exist_ok=True)
        missing = [
            relative
            for relative in asset_files
            if not (uploads_target / relative).is_file()
        ]
        if missing:
            raise RuntimeError(
                "backup is incomplete; assets missing from uploads: "
                + ", ".join(missing[:5])
            )
        file_count, total_bytes, tree_hash = _tree_hash(uploads_target)
        manifest = {
            "format": "c-notes-paired-backup-v1",
            "created_at": utcnow().isoformat(),
            "app_version": settings.app_version,
            "database": _redacted_database(settings.database_url),
            "db_dump": dump_path.name,
            "db_sha256": _sha256_file(dump_path),
            "uploads_file_count": file_count,
            "uploads_bytes": total_bytes,
            "uploads_sha256": tree_hash,
            "asset_count": len(asset_files),
            "asset_files": asset_files,
        }
        (backup_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return backup_dir
    finally:
        try:
            lock_connection.execute(
                "SELECT pg_advisory_unlock(%s)", (BACKUP_LOCK_KEY,)
            )
        finally:
            lock_connection.close()


def verify_backup(backup_dir: Path) -> dict:
    manifest_path = backup_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dump_path = backup_dir / manifest["db_dump"]
    if _sha256_file(dump_path) != manifest["db_sha256"]:
        raise RuntimeError("database dump checksum mismatch")
    file_count, total_bytes, tree_hash = _tree_hash(backup_dir / "uploads")
    if (
        file_count != manifest["uploads_file_count"]
        or total_bytes != manifest["uploads_bytes"]
        or tree_hash != manifest["uploads_sha256"]
    ):
        raise RuntimeError("uploads backup checksum mismatch")
    for relative in manifest.get("asset_files", []):
        if not (backup_dir / "uploads" / relative).is_file():
            raise RuntimeError(f"asset file missing from backup: {relative}")
    return manifest


def restore_backup(
    backup_dir: Path,
    database_url: str,
    uploads_dir: Path,
    *,
    force: bool,
) -> dict:
    manifest = verify_backup(backup_dir)
    if not force:
        raise RuntimeError("restore requires --force")
    database_target, database_env = _database_tool_target(database_url)
    lock_connection = psycopg.connect(
        _database_url_for_connection(database_url),
        autocommit=True,
    )
    previous = None
    try:
        lock_connection.execute(
            "SELECT pg_advisory_lock(%s)", (BACKUP_LOCK_KEY,)
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        staging = uploads_dir.parent / f".{uploads_dir.name}.restoring-{stamp}"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(backup_dir / "uploads", staging)

        _run(
            [
                _tool("pg_restore"),
                "--dbname",
                database_target,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                str(backup_dir / manifest["db_dump"]),
            ],
            env=database_env,
        )

        if uploads_dir.exists():
            previous = uploads_dir.parent / f"{uploads_dir.name}.pre-restore-{stamp}"
            shutil.move(str(uploads_dir), str(previous))
        shutil.move(str(staging), str(uploads_dir))
        return {
            "manifest": manifest,
            "database": _redacted_database(database_url),
            "uploads_dir": str(uploads_dir),
            "previous_uploads": str(previous) if previous else None,
        }
    finally:
        try:
            lock_connection.execute(
                "SELECT pg_advisory_unlock(%s)", (BACKUP_LOCK_KEY,)
            )
        finally:
            lock_connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paired PostgreSQL + uploads backup and restore"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--backup-dir", type=Path, default=None)
    backup_parser.add_argument(
        "--uploads-dir", type=Path, default=settings.uploads_path
    )

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("backup_dir", type=Path)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup_dir", type=Path)
    restore_parser.add_argument("--database-url", required=True)
    restore_parser.add_argument(
        "--uploads-dir", type=Path, default=settings.uploads_path
    )
    restore_parser.add_argument("--force", action="store_true")

    args = parser.parse_args()
    if args.command == "backup":
        target = args.backup_dir or (
            settings.backup_path
            / f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )
        result = create_backup(target, args.uploads_dir)
        print(json.dumps({"backup_dir": str(result)}, ensure_ascii=False))
    elif args.command == "verify":
        manifest = verify_backup(args.backup_dir)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        result = restore_backup(
            args.backup_dir,
            args.database_url,
            args.uploads_dir,
            force=args.force,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

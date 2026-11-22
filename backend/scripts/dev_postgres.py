"""Start/stop the local PostgreSQL 16 used for development.

This is a convenience for Windows/offline development. Production should use
an external PostgreSQL instance configured through DATABASE_URL.

The data directory and binaries live under an ASCII user-local path because
PostgreSQL initdb does not handle this project's Chinese path on Windows.
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

LOCAL_APP_DIR = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")
) / "cqoder-pg"
PGDATA = LOCAL_APP_DIR / "pgdata"
PGINSTALL = LOCAL_APP_DIR / "pginstall"
LOG_FILE = LOCAL_APP_DIR / "postgres.log"
PORT = 55432
HOST = "127.0.0.1"
DATABASE = "c_notes"


def binary(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return PGINSTALL / "bin" / f"{name}{suffix}"


def ensure_binaries() -> None:
    import pgserver

    if (binary("initdb")).exists():
        return
    package_install = Path(pgserver.__file__).resolve().parent / "pginstall"
    LOCAL_APP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package_install, PGINSTALL)


def run(command: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=LOCAL_APP_DIR,
        env=env or os.environ.copy(),
        text=True,
        capture_output=True,
        check=check,
    )


def is_running() -> bool:
    if not (PGDATA / "PG_VERSION").exists():
        return False
    result = run([str(binary("pg_ctl")), "-D", str(PGDATA), "status"], check=False)
    return result.returncode == 0


def start() -> None:
    ensure_binaries()
    LOCAL_APP_DIR.mkdir(parents=True, exist_ok=True)
    if not (PGDATA / "PG_VERSION").exists():
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        result = run(
            [
                str(binary("initdb")),
                "-D",
                str(PGDATA),
                "--auth=trust",
                "--auth-local=trust",
                "--encoding=UTF8",
                "--locale=C",
                "-U",
                "postgres",
            ],
            env=env,
        )
        print(result.stdout.strip())

    if not is_running():
        result = run(
            [
                str(binary("pg_ctl")),
                "-D",
                str(PGDATA),
                "-o",
                f"-p {PORT} -h {HOST}",
                "-l",
                str(LOG_FILE),
                "-w",
                "start",
            ]
        )
        print(result.stdout.strip())

    ready = run(
        [str(binary("pg_isready")), "-h", HOST, "-p", str(PORT)],
        check=False,
    )
    if ready.returncode != 0:
        raise SystemExit(f"PostgreSQL is not ready: {ready.stderr or ready.stdout}")

    exists = run(
        [
            str(binary("psql")),
            "-h",
            HOST,
            "-p",
            str(PORT),
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname = '{DATABASE}'",
        ],
        check=False,
    )
    if exists.stdout.strip() != "1":
        run(
            [
                str(binary("createdb")),
                "-h",
                HOST,
                "-p",
                str(PORT),
                "-U",
                "postgres",
                DATABASE,
            ]
        )

    print(
        "DATABASE_URL="
        f"postgresql+psycopg://postgres@{HOST}:{PORT}/{DATABASE}"
    )


def stop() -> None:
    if not is_running():
        print("PostgreSQL is not running")
        return
    result = run([str(binary("pg_ctl")), "-D", str(PGDATA), "-m", "fast", "stop"])
    print(result.stdout.strip())


def status() -> None:
    if is_running():
        print(f"PostgreSQL is running on {HOST}:{PORT}")
    else:
        print("PostgreSQL is not running")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    {"start": start, "stop": stop, "status": status}[args.action]()


if __name__ == "__main__":
    main()

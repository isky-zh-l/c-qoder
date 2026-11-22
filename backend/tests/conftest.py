import atexit
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from aiosmtpd.controller import Controller
from fastapi.testclient import TestClient
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for path in (BACKEND_DIR, TESTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

TEST_UPLOADS = Path(tempfile.mkdtemp(prefix="cqoder-uploads-"))
os.environ["PUBLIC_BASE_PATH"] = "/c"
os.environ["API_PREFIX"] = "/api/v1"
os.environ["UPLOADS_DIR"] = str(TEST_UPLOADS)
os.environ["STORAGE_TMP_DIR"] = str(TEST_UPLOADS / "tmp")
os.environ["EXPORTS_DIR"] = str(TEST_UPLOADS / "exports")
os.environ["BACKUP_DIR"] = str(TEST_UPLOADS / "backups")
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["SESSION_COOKIE_NAME"] = "c_session"
os.environ["RATE_LIMIT_REQUEST_PER_MINUTE"] = "100000"
os.environ["RATE_LIMIT_REGISTER_PER_HOUR"] = "4"
os.environ["RATE_LIMIT_LOGIN_PER_15MIN"] = "5"
os.environ["RATE_LIMIT_VERIFY_PER_HOUR"] = "5"
os.environ["RATE_LIMIT_RESEND_PER_HOUR"] = "2"
os.environ["RATE_LIMIT_FORGOT_PER_HOUR"] = "2"
os.environ["RATE_LIMIT_CHANGE_PASSWORD_PER_HOUR"] = "3"
os.environ["LC_ALL"] = "C"
os.environ["LANG"] = "C"


MAILBOX: list[bytes] = []


class _SmtpHandler:
    async def handle_DATA(self, server, session, envelope):
        MAILBOX.append(envelope.content)
        return "250 Message accepted for delivery"


def _start_smtp():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    controller = Controller(
        _SmtpHandler(),
        hostname="127.0.0.1",
        port=port,
    )
    controller.start()
    return controller, port


SMTP_CONTROLLER, SMTP_PORT = _start_smtp()
os.environ["SMTP_HOST"] = "127.0.0.1"
os.environ["SMTP_PORT"] = str(SMTP_PORT)
os.environ["SMTP_FROM"] = "notes@test.local"
os.environ["SMTP_STARTTLS"] = "false"
os.environ["SMTP_USERNAME"] = ""
os.environ["SMTP_PASSWORD"] = ""


def _prepare_pgserver():
    import pgserver
    from pgserver import _commands

    install_dir = Path(pgserver.__file__).resolve().parent / "pginstall"
    ascii_bin = Path(tempfile.gettempdir()) / "cqoder-pg-bin"
    initdb_name = "initdb.exe" if os.name == "nt" else "initdb"
    if not (ascii_bin / "bin" / initdb_name).exists():
        if ascii_bin.exists():
            shutil.rmtree(ascii_bin, ignore_errors=True)
        shutil.copytree(install_dir, ascii_bin)
    _commands.POSTGRES_BIN_PATH = ascii_bin / "bin"

    root = Path(tempfile.mkdtemp(prefix="cqoder-pgdata-", dir=tempfile.gettempdir()))
    server = pgserver.get_server(root / "data", cleanup_mode="delete")
    return server, root


PG_SERVER, PG_ROOT = _prepare_pgserver()
PG_URL = PG_SERVER.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
os.environ["DATABASE_URL"] = PG_URL

_alembic = subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=BACKEND_DIR,
    env=os.environ.copy(),
    capture_output=True,
    text=True,
)
if _alembic.returncode != 0:
    raise RuntimeError(
        "Alembic upgrade failed in test PostgreSQL:\n"
        f"stdout:\n{_alembic.stdout}\nstderr:\n{_alembic.stderr}"
    )

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.users import create_user  # noqa: E402

from helpers import (  # noqa: E402
    API,
    PASSWORD_ADMIN,
    PASSWORD_ALICE,
    PASSWORD_BOB,
)

if engine.url.database != "postgres" or engine.url.port == 55432:
    raise RuntimeError(f"Unsafe test database URL: {engine.url!r}")


def _shutdown():
    try:
        SMTP_CONTROLLER.stop()
    except Exception:
        pass
    try:
        PG_SERVER.cleanup()
    except Exception:
        pass
    shutil.rmtree(PG_ROOT, ignore_errors=True)
    shutil.rmtree(TEST_UPLOADS, ignore_errors=True)


atexit.register(_shutdown)


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE users, user_profiles, sessions, auth_tokens, "
                "chapters, documents, blocks, assets, document_favorites, "
                "document_publications, recycle_entries, rate_limits, "
                "storage_reservations, admin_audit_logs "
                "RESTART IDENTITY CASCADE"
            )
        )
    shutil.rmtree(TEST_UPLOADS, ignore_errors=True)
    TEST_UPLOADS.mkdir(parents=True, exist_ok=True)
    MAILBOX.clear()
    yield


@pytest.fixture
def db_session(clean_db):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_user(
    db, email, password, name, *, verified=True, enabled=True, is_admin=False
):
    return create_user(
        db,
        email=email,
        password=password,
        display_name=name,
        verified=verified,
        enabled=enabled,
        is_admin=is_admin,
    )


@pytest.fixture
def alice(db_session):
    return _make_user(db_session, "alice@example.com", PASSWORD_ALICE, "Alice")


@pytest.fixture
def bob(db_session):
    return _make_user(db_session, "bob@example.com", PASSWORD_BOB, "Bob")


@pytest.fixture
def admin(db_session):
    user = _make_user(
        db_session,
        "admin@example.com",
        PASSWORD_ADMIN,
        "Admin",
        is_admin=True,
    )
    return user


def _login_client(email, password):
    client = TestClient(app)
    response = client.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    csrf_token = response.json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": csrf_token})
    return client


@pytest.fixture
def login_as():
    return _login_client


@pytest.fixture
def alice_client(alice):
    return _login_client(alice.email, PASSWORD_ALICE)


@pytest.fixture
def bob_client(bob):
    return _login_client(bob.email, PASSWORD_BOB)


@pytest.fixture
def admin_client(admin):
    return _login_client(admin.email, PASSWORD_ADMIN)


@pytest.fixture
def anon_client():
    return TestClient(app)


@pytest.fixture
def make_test_user(db_session):
    def factory(email: str, password: str, name: str, **kwargs):
        return _make_user(db_session, email, password, name, **kwargs)

    return factory


@pytest.fixture
def mailbox():
    return MAILBOX

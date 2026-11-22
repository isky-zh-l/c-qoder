from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.routers.auth as auth_router
from app.models import AuthToken, User
from app.security import hash_token, utcnow
from app.services.email import EmailDeliveryError
from app.services.workspace import DEFAULT_CHAPTERS, initialize_user_workspace
from helpers import (
    API,
    PASSWORD_ALICE,
    email_link,
    password_reset_token,
    register_user,
    verification_token,
)

API_BASE = "/c/api/v1"


def test_register_verify_login_defaults_and_idempotent_init(
    anon_client, login_as, mailbox, db_session
):
    email = "NewUser@Example.com"
    password = "new-user-password-123"
    response = register_user(anon_client, email, password, "New User")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert "token" not in response.text.lower()
    assert "http" not in response.text.lower()
    assert len(mailbox) == 1
    link = email_link(mailbox, "/verify-email")
    assert link.startswith("http://testserver/c/verify-email?token=")

    before_verify = anon_client.post(
        f"{API}/auth/login",
        json={"email": email.lower(), "password": password},
    )
    assert before_verify.status_code == 403
    assert before_verify.json()["error"]["code"] == "email_not_verified"

    token = verification_token(mailbox)
    token_row = db_session.scalar(
        select(AuthToken)
        .where(AuthToken.purpose == "email_verify")
        .order_by(AuthToken.id.desc())
    )
    assert token_row is not None
    assert token_row.token_hash == hash_token(token)
    assert token_row.token_hash != token

    verified = anon_client.post(
        f"{API}/auth/verify-email", json={"token": token}
    )
    assert verified.status_code == 204
    reused = anon_client.post(
        f"{API}/auth/verify-email", json={"token": token}
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "invalid_token"

    client = login_as(email.lower(), password)
    chapters = client.get(f"{API}/chapters")
    assert chapters.status_code == 200
    chapter_names = [chapter["name"] for chapter in chapters.json()]
    assert len(chapter_names) == 12
    assert chapter_names == list(DEFAULT_CHAPTERS)
    assert client.get(f"{API}/documents?scope=library").json() == []
    me = client.get(f"{API}/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "New User"

    user = db_session.scalar(select(User).where(User.email == email.lower()))
    assert user is not None
    assert user.workspace_initialized_at is not None
    initialize_user_workspace(db_session, user.id)
    initialize_user_workspace(db_session, user.id)
    db_session.commit()
    assert client.get(f"{API}/chapters").json() is not None
    assert len(client.get(f"{API}/chapters").json()) == 12


def test_verification_token_expiry_resend_and_invalidation(
    anon_client, mailbox, db_session
):
    email = "expiry@example.com"
    password = "expiry-password-123"
    response = register_user(anon_client, email, password)
    assert response.status_code == 201
    first_token = verification_token(mailbox)

    token_row = db_session.scalar(
        select(AuthToken)
        .where(AuthToken.purpose == "email_verify")
        .order_by(AuthToken.id.desc())
    )
    token_row.expires_at = utcnow() - timedelta(minutes=1)
    db_session.commit()

    expired = anon_client.post(
        f"{API}/auth/verify-email", json={"token": first_token}
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "invalid_token"

    resend = anon_client.post(
        f"{API}/auth/resend-verification", json={"email": email}
    )
    assert resend.status_code == 202
    assert len(mailbox) == 2
    second_token = verification_token(mailbox)
    assert second_token != first_token

    old_again = anon_client.post(
        f"{API}/auth/verify-email", json={"token": first_token}
    )
    assert old_again.status_code == 400

    verified = anon_client.post(
        f"{API}/auth/verify-email", json={"token": second_token}
    )
    assert verified.status_code == 204
    reused = anon_client.post(
        f"{API}/auth/verify-email", json={"token": second_token}
    )
    assert reused.status_code == 400


def test_forgot_is_generic_and_reset_invalidates_sessions(
    alice, alice_client, anon_client, login_as, mailbox, db_session
):
    forgot = anon_client.post(
        f"{API}/auth/forgot-password", json={"email": alice.email}
    )
    assert forgot.status_code == 202
    assert len(mailbox) == 1

    before_count = len(mailbox)
    missing = anon_client.post(
        f"{API}/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert missing.status_code == 202
    assert len(mailbox) == before_count

    reset_token = password_reset_token(mailbox)
    new_password = "reset-password-456"
    reset = anon_client.post(
        f"{API}/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert reset.status_code == 204
    reused = anon_client.post(
        f"{API}/auth/reset-password",
        json={"token": reset_token, "new_password": "another-password-456"},
    )
    assert reused.status_code == 400

    assert alice_client.get(f"{API}/chapters").status_code == 401
    assert (
        anon_client.post(
            f"{API}/auth/login",
            json={"email": alice.email, "password": PASSWORD_ALICE},
        ).status_code
        == 401
    )
    new_client = login_as(alice.email, new_password)
    assert new_client.get(f"{API}/chapters").status_code == 200


def test_logout_current_session_change_password_all_sessions(
    alice, alice_client, anon_client, login_as
):
    second = login_as(alice.email, PASSWORD_ALICE)
    assert alice_client.post(f"{API}/auth/logout").status_code == 204
    assert alice_client.get(f"{API}/chapters").status_code == 401
    assert second.get(f"{API}/chapters").status_code == 200

    current = login_as(alice.email, PASSWORD_ALICE)
    change = current.post(
        f"{API}/auth/change-password",
        json={
            "current_password": PASSWORD_ALICE,
            "new_password": "changed-password-789",
        },
    )
    assert change.status_code == 204
    assert current.get(f"{API}/chapters").status_code == 401
    assert second.get(f"{API}/chapters").status_code == 401

    old_login = anon_client.post(
        f"{API}/auth/login",
        json={"email": alice.email, "password": PASSWORD_ALICE},
    )
    assert old_login.status_code == 401
    new_client = login_as(alice.email, "changed-password-789")
    assert new_client.get(f"{API}/chapters").status_code == 200


def test_login_sets_httponly_cookie_flags_and_same_site_path(alice):
    from app.main import app

    client = TestClient(app)
    response = client.post(
        f"{API}/auth/login",
        json={"email": alice.email, "password": PASSWORD_ALICE},
    )
    assert response.status_code == 200
    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(
        value for value in cookie_headers if value.startswith("c_session=")
    )
    csrf_cookie = next(
        value for value in cookie_headers if value.startswith("c_csrf=")
    )
    for header in (session_cookie, csrf_cookie):
        lowered = header.lower()
        assert "httponly" in lowered
        assert "samesite=lax" in lowered
        assert "path=/c" in lowered


def test_csrf_required_for_authenticated_writes(alice_client):
    csrf = alice_client.headers.get("X-CSRF-Token")
    assert csrf
    alice_client.headers.pop("X-CSRF-Token", None)
    response = alice_client.post(f"{API}/chapters", json={"name": "No CSRF"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    alice_client.headers.update({"X-CSRF-Token": csrf})
    assert alice_client.post(
        f"{API}/chapters", json={"name": "With CSRF"}
    ).status_code == 201


def test_origin_guard(anon_client, alice):
    denied = anon_client.post(
        f"{API}/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": alice.email, "password": PASSWORD_ALICE},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "origin_not_allowed"

    allowed = anon_client.post(
        f"{API}/auth/login",
        headers={"Origin": "http://testserver"},
        json={"email": alice.email, "password": PASSWORD_ALICE},
    )
    assert allowed.status_code == 200


def test_register_rate_limit_login_rate_limit_and_forgot_rate_limit(
    anon_client, mailbox
):
    emails = [
        "r1@example.com",
        "r2@example.com",
        "r3@example.com",
        "r4@example.com",
        "r5@example.com",
    ]
    for index, email in enumerate(emails):
        response = anon_client.post(
            f"{API}/auth/register",
            json={"email": email, "password": "rate-limit-password-123"},
        )
        if index < 4:
            assert response.status_code == 201, response.text
        else:
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "rate_limited"

    for _ in range(5):
        response = anon_client.post(
            f"{API}/auth/login",
            json={
                "email": "login-limit@example.com",
                "password": "wrong-password-123",
            },
        )
        assert response.status_code == 401
    limited_login = anon_client.post(
        f"{API}/auth/login",
        json={
            "email": "login-limit@example.com",
            "password": "wrong-password-123",
        },
    )
    assert limited_login.status_code == 429
    assert limited_login.headers.get("Retry-After")

    for _ in range(2):
        assert (
            anon_client.post(
                f"{API}/auth/forgot-password",
                json={"email": "forgot-limit@example.com"},
            ).status_code
            == 202
        )
    limited_forgot = anon_client.post(
        f"{API}/auth/forgot-password",
        json={"email": "forgot-limit@example.com"},
    )
    assert limited_forgot.status_code == 429


def test_verify_and_resend_rate_limits(anon_client):
    register_user(anon_client, "verify-limit@example.com", "verify-limit-123")
    for _ in range(5):
        response = anon_client.post(
            f"{API}/auth/verify-email", json={"token": "x" * 30}
        )
        assert response.status_code == 400
    limited_verify = anon_client.post(
        f"{API}/auth/verify-email", json={"token": "x" * 30}
    )
    assert limited_verify.status_code == 429

    for _ in range(2):
        assert (
            anon_client.post(
                f"{API}/auth/resend-verification",
                json={"email": "verify-limit@example.com"},
            ).status_code
            == 202
        )
    limited_resend = anon_client.post(
        f"{API}/auth/resend-verification",
        json={"email": "verify-limit@example.com"},
    )
    assert limited_resend.status_code == 429


def test_registration_duplicate_case_and_concurrent_unique(
    anon_client, db_session, mailbox
):
    first = register_user(
        anon_client, "CaseSensitive@Example.com", "case-password-123"
    )
    assert first.status_code == 201
    duplicate = register_user(
        anon_client, "casesensitive@example.com", "case-password-123"
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_taken"

    from app.main import app

    def register_concurrently(_):
        client = TestClient(app)
        return client.post(
            f"{API}/auth/register",
            json={
                "email": "race@example.com",
                "password": "race-password-123",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(register_concurrently, range(2)))
    assert statuses.count(201) == 1
    assert statuses.count(409) == 1
    assert (
        db_session.scalar(
            select(func.count()).select_from(User).where(
                User.email == "race@example.com"
            )
        )
        == 1
    )


def test_registration_email_failure_is_truthful(
    anon_client, monkeypatch, db_session
):
    def fail_send(*_args, **_kwargs):
        raise EmailDeliveryError("smtp down")

    monkeypatch.setattr(auth_router, "send_verification_email", fail_send)
    response = register_user(
        anon_client,
        "mail-failure@example.com",
        "mail-failure-password-123",
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "email_delivery_failed"
    assert "token" not in response.text.lower()
    assert "http" not in response.text.lower()

    user = db_session.scalar(
        select(User).where(User.email == "mail-failure@example.com")
    )
    assert user is not None
    assert user.email_verified_at is None


def test_email_not_configured_is_reported_without_creating_user(
    anon_client, monkeypatch, db_session
):
    monkeypatch.setattr(auth_router, "email_is_configured", lambda: False)
    response = register_user(
        anon_client,
        "no-mail@example.com",
        "no-mail-password-123",
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "email_not_configured"
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email == "no-mail@example.com")
        )
        == 0
    )
    assert (
        anon_client.post(
            f"{API}/auth/resend-verification",
            json={"email": "no-mail@example.com"},
        ).status_code
        == 503
    )
    assert (
        anon_client.post(
            f"{API}/auth/forgot-password",
            json={"email": "no-mail@example.com"},
        ).status_code
        == 503
    )

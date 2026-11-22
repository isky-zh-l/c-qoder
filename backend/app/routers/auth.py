import hmac
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_auth, get_optional_auth
from app.config import get_settings
from app.csrf import require_csrf
from app.db import get_db
from app.errors import ApiError
from app.models import AuthSession, AuthToken, User, UserProfile
from app.schemas import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    LoginOut,
    MessageOut,
    RegisterIn,
    RegisterOut,
    ResendVerificationIn,
    ResetPasswordIn,
    SessionOut,
    VerifyEmailIn,
)
from app.security import (
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    utcnow,
    verify_password,
)
from app.services.email import (
    EmailDeliveryError,
    EmailNotConfigured,
    is_configured as email_is_configured,
    send_password_reset_email,
    send_verification_email,
)
from app.services.rate_limit import consume_rate_limit
from app.services.settings import registration_enabled
from app.services.tokens import issue_token, require_valid_token
from app.services.users import user_out
from app.services.workspace import initialize_user_workspace

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("c_notes.auth")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _ensure_email_configured() -> None:
    if not email_is_configured():
        raise ApiError(
            503,
            "email_not_configured",
            "邮件服务尚未配置，暂时无法完成邮箱操作",
        )


def _set_auth_cookies(
    response: Response, session_token: str, csrf_token: str
) -> None:
    max_age = settings.session_ttl_days * 86400
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=settings.session_cookie_path,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=settings.session_cookie_path,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path=settings.session_cookie_path,
    )


def _new_csrf_token(db: Session, session: AuthSession) -> str:
    token = generate_token()
    session.csrf_token_hash = hash_token(token)
    return token


def _generic_email_message() -> MessageOut:
    return MessageOut(
        message="请求已接收。如果该邮箱已注册，请检查收件箱；未收到可稍后重试"
    )


@router.post("/auth/register", response_model=RegisterOut, status_code=201)
def register(
    payload: RegisterIn,
    request: Request,
    db: Session = Depends(get_db),
):
    if not registration_enabled(db):
        raise ApiError(403, "registration_disabled", "注册暂未开放")
    _ensure_email_configured()
    ip = _client_ip(request)
    consume_rate_limit(
        "register",
        ip,
        settings.rate_limit_register_per_hour,
        3600,
    )

    email = normalize_email(str(payload.email))
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        email_verified_at=None,
        is_enabled=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "email_taken", "该邮箱已注册")

    db.add(
        UserProfile(
            user_id=user.id,
            display_name=(payload.display_name or email.split("@", 1)[0]),
            bio="",
        )
    )
    db.flush()
    initialize_user_workspace(db, user.id)
    verification_token = issue_token(
        db,
        user_id=user.id,
        purpose="email_verify",
        ttl_hours=settings.email_verify_ttl_hours,
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "email_taken", "该邮箱已注册")

    try:
        send_verification_email(email, verification_token)
    except (EmailDeliveryError, EmailNotConfigured):
        logger.exception("Verification email delivery failed for user %s", user.id)
        raise ApiError(
            503,
            "email_delivery_failed",
            "账号已创建，但验证邮件发送失败，请稍后重发验证邮件",
        )

    return RegisterOut(message="验证邮件已发送", email=email)


@router.post("/auth/verify-email", status_code=204)
def verify_email(
    payload: VerifyEmailIn,
    request: Request,
    db: Session = Depends(get_db),
):
    consume_rate_limit(
        "verify_email",
        _client_ip(request),
        settings.rate_limit_verify_per_hour,
        3600,
    )
    token = require_valid_token(db, payload.token, "email_verify")
    user = db.get(User, token.user_id)
    if user is None:
        raise ApiError(400, "invalid_token", "链接无效、已过期或已使用")

    now = utcnow()
    token.consumed_at = now
    if user.email_verified_at is None:
        user.email_verified_at = now
    db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == "email_verify",
            AuthToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.commit()


@router.post(
    "/auth/resend-verification",
    response_model=MessageOut,
    status_code=202,
)
def resend_verification(
    payload: ResendVerificationIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _ensure_email_configured()
    email = normalize_email(str(payload.email))
    consume_rate_limit(
        "resend_verification",
        f"{_client_ip(request)}:{email}",
        settings.rate_limit_resend_per_hour,
        3600,
    )

    user = db.scalar(select(User).where(User.email == email))
    if (
        user is None
        or user.email_verified_at is not None
        or not user.is_enabled
    ):
        return _generic_email_message()

    token = issue_token(
        db,
        user_id=user.id,
        purpose="email_verify",
        ttl_hours=settings.email_verify_ttl_hours,
    )
    db.commit()
    try:
        send_verification_email(email, token)
    except (EmailDeliveryError, EmailNotConfigured):
        logger.exception("Resend verification email failed for user %s", user.id)
    return _generic_email_message()


@router.post("/auth/login", response_model=LoginOut)
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = normalize_email(str(payload.email))
    consume_rate_limit(
        "login",
        f"{_client_ip(request)}:{email}",
        settings.rate_limit_login_per_15min,
        900,
    )
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(user.password_hash, payload.password):
        raise ApiError(401, "invalid_credentials", "邮箱或密码不正确")
    if not user.is_enabled:
        raise ApiError(403, "account_disabled", "账号已停用")
    if user.email_verified_at is None:
        raise ApiError(403, "email_not_verified", "邮箱尚未验证")

    session_token = generate_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(session_token),
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
    )
    csrf_token = _new_csrf_token(db, session)
    db.add(session)
    db.commit()
    _set_auth_cookies(response, session_token, csrf_token)
    return LoginOut(user=user_out(db, user), csrf_token=csrf_token)


@router.post(
    "/auth/logout",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def logout(
    response: Response,
    auth=Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    session, _user = auth
    session.revoked_at = utcnow()
    db.commit()
    _clear_auth_cookies(response)


@router.get("/auth/session", response_model=SessionOut)
def session_info(
    request: Request,
    response: Response,
    auth=Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    if auth is None:
        return SessionOut(authenticated=False, user=None, csrf_token=None)

    session, user = auth
    csrf_token = request.cookies.get(settings.csrf_cookie_name)
    if (
        not csrf_token
        or not session.csrf_token_hash
        or not hmac.compare_digest(
            hash_token(csrf_token), session.csrf_token_hash
        )
    ):
        csrf_token = _new_csrf_token(db, session)
        db.commit()
        response.set_cookie(
            key=settings.csrf_cookie_name,
            value=csrf_token,
            max_age=settings.session_ttl_days * 86400,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path=settings.session_cookie_path,
        )
    return SessionOut(
        authenticated=True,
        user=user_out(db, user),
        csrf_token=csrf_token,
    )


@router.post(
    "/auth/forgot-password",
    response_model=MessageOut,
    status_code=202,
)
def forgot_password(
    payload: ForgotPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _ensure_email_configured()
    email = normalize_email(str(payload.email))
    consume_rate_limit(
        "forgot_password",
        f"{_client_ip(request)}:{email}",
        settings.rate_limit_forgot_per_hour,
        3600,
    )

    user = db.scalar(select(User).where(User.email == email))
    if (
        user is None
        or user.email_verified_at is None
        or not user.is_enabled
    ):
        return _generic_email_message()

    token = issue_token(
        db,
        user_id=user.id,
        purpose="password_reset",
        ttl_hours=settings.password_reset_ttl_hours,
    )
    db.commit()
    try:
        send_password_reset_email(email, token)
    except (EmailDeliveryError, EmailNotConfigured):
        logger.exception("Password reset email failed for user %s", user.id)
    return _generic_email_message()


@router.post("/auth/reset-password", status_code=204)
def reset_password(
    payload: ResetPasswordIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    consume_rate_limit(
        "password_reset",
        _client_ip(request),
        settings.rate_limit_verify_per_hour,
        3600,
    )
    token = require_valid_token(db, payload.token, "password_reset")
    user = db.get(User, token.user_id)
    if user is None:
        raise ApiError(400, "invalid_token", "链接无效、已过期或已使用")

    now = utcnow()
    user.password_hash = hash_password(payload.new_password)
    token.consumed_at = now
    db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == "password_reset",
            AuthToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
    _clear_auth_cookies(response)


@router.post(
    "/auth/change-password",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def change_password(
    payload: ChangePasswordIn,
    response: Response,
    auth=Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    session, user = auth
    consume_rate_limit(
        "change_password",
        str(user.id),
        settings.rate_limit_change_password_per_hour,
        3600,
    )
    if not verify_password(user.password_hash, payload.current_password):
        raise ApiError(400, "invalid_credentials", "当前密码不正确")

    now = utcnow()
    user.password_hash = hash_password(payload.new_password)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    session.revoked_at = now
    db.commit()
    _clear_auth_cookies(response)

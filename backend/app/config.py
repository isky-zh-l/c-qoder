import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower() or "development"
ENV_FILES = tuple(
    str(path)
    for path in (
        BACKEND_DIR / ".env",
        BACKEND_DIR / f".env.{APP_ENV}",
    )
    if path.is_file()
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # APP_ENV=production loads .env first, then .env.production overrides it.
        env_file=ENV_FILES or None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_version: str = "0.1.0"
    public_base_path: str = "/c"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres@127.0.0.1:55432/c_notes"
    site_title: str = "C 语言学习笔记"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    frontend_dist: str = "../frontend/dist"
    uploads_dir: str = "data/uploads"
    public_base_url: str = "http://127.0.0.1:8000"
    session_cookie_name: str = "c_session"
    csrf_cookie_name: str = "c_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    session_cookie_secure: bool = False
    session_ttl_days: int = 30
    email_verify_ttl_hours: int = 24
    password_reset_ttl_hours: int = 1
    recycle_retention_days: int = 7
    account_deletion_retention_days: int = 30
    default_user_storage_bytes: int = 100 * 1024 * 1024
    max_file_bytes: int = 2 * 1024 * 1024
    max_image_bytes: int = 10 * 1024 * 1024
    image_max_dimension: int = 10000
    upload_reservation_minutes: int = 10
    storage_orphan_grace_hours: int = 24
    storage_tmp_dir: str = "data/tmp"
    exports_dir: str = "data/exports"
    backup_dir: str = "data/backups"
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = False
    smtp_timeout: int = 10
    rate_limit_enabled: bool = True
    rate_limit_request_per_minute: int = 600
    rate_limit_register_per_hour: int = 5
    rate_limit_login_per_15min: int = 10
    rate_limit_verify_per_hour: int = 10
    rate_limit_resend_per_hour: int = 3
    rate_limit_forgot_per_hour: int = 3
    rate_limit_change_password_per_hour: int = 5

    @field_validator("public_base_path")
    @classmethod
    def validate_public_base_path(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith("/"):
            raise ValueError("PUBLIC_BASE_PATH 必须以 / 开头")
        if normalized == "":
            raise ValueError("PUBLIC_BASE_PATH 不能是根路径，请使用 /c 这类子目录")
        return normalized

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = "/" + value.strip().strip("/")
        if normalized == "/":
            raise ValueError("API_PREFIX 不能为空")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL 必须使用 postgresql+psycopg:// 连接 PostgreSQL"
            )
        return value

    @property
    def api_base_path(self) -> str:
        return f"{self.public_base_path}{self.api_prefix}"

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS 不允许通配符，必须列出实际站点来源")
        return ",".join(origins)

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            raise ValueError("PUBLIC_BASE_URL 必须是 http(s) 地址")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_origins(self) -> set[str]:
        return set(self.cors_origin_list) | {self.public_base_url}

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def frontend_dist_path(self) -> Path:
        path = Path(self.frontend_dist)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve()

    def _data_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve()

    @property
    def uploads_path(self) -> Path:
        return self._data_path(self.uploads_dir)

    @property
    def storage_tmp_path(self) -> Path:
        return self._data_path(self.storage_tmp_dir)

    @property
    def exports_path(self) -> Path:
        return self._data_path(self.exports_dir)

    @property
    def backup_path(self) -> Path:
        return self._data_path(self.backup_dir)

    @property
    def session_cookie_path(self) -> str:
        return self.public_base_path or "/"


@lru_cache
def get_settings() -> Settings:
    return Settings()

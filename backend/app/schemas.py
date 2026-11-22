from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator, model_validator


def to_iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(InputModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class RegisterIn(InputModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("显示名不能为空")
        return cleaned


class VerifyEmailIn(InputModel):
    token: str = Field(min_length=20, max_length=200)


class ResendVerificationIn(InputModel):
    email: EmailStr


class ForgotPasswordIn(InputModel):
    email: EmailStr


class ResetPasswordIn(InputModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)


class ChangePasswordIn(InputModel):
    current_password: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    bio: str
    avatar_asset_id: int | None
    email_verified_at: datetime | None
    is_enabled: bool
    is_admin: bool
    created_at: datetime

    @field_serializer("email_verified_at", "created_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        return to_iso_utc(value)


class SessionOut(BaseModel):
    authenticated: bool
    user: UserOut | None
    csrf_token: str | None = None


class LoginOut(BaseModel):
    user: UserOut
    csrf_token: str


class RegisterOut(BaseModel):
    message: str
    email: str


class MessageOut(BaseModel):
    message: str


class ProfileUpdate(InputModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=2000)
    avatar_asset_id: int | None = None

    @field_validator("display_name", "bio")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if value is not None and not cleaned and value != "":
            raise ValueError("不能只包含空白")
        return cleaned


class HealthOut(BaseModel):
    status: str
    database: str
    uploads: str
    version: str


class PublicSiteOut(BaseModel):
    site_title: str
    registration_enabled: bool


class ChapterCreate(InputModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("章节名不能为空")
        return cleaned


class ChapterUpdate(ChapterCreate):
    pass


class ChapterOut(BaseModel):
    id: int
    name: str
    sort_order: int
    document_count: int


class ChapterOrderIn(InputModel):
    chapter_ids: list[int] = Field(default_factory=list)


class WorkspaceStorageOut(BaseModel):
    asset_count: int
    total_bytes: int


class StorageLimitsOut(BaseModel):
    max_file_bytes: int
    max_image_bytes: int
    image_max_dimension: int


class StorageUsageOut(BaseModel):
    quota_bytes: int
    used_bytes: int
    reserved_bytes: int
    remaining_bytes: int
    source_bytes: int
    note_bytes: int
    image_bytes: int
    recycle_bytes: int
    publication_bytes: int
    asset_count: int
    document_count: int
    recycle_count: int
    over_quota: bool
    limits: StorageLimitsOut
    recycle_retention_days: int
    account_deletion_retention_days: int


class AccountDeleteIn(InputModel):
    current_password: str = Field(min_length=10, max_length=128)
    confirmation: str = Field(min_length=1, max_length=32)


class AccountDeletionOut(BaseModel):
    message: str
    purge_after: datetime
    retention_days: int

    @field_serializer("purge_after")
    def serialize_purge_after(self, value: datetime) -> str:
        return to_iso_utc(value) or ""


class WorkspaceOut(BaseModel):
    user: UserOut
    chapters: list[ChapterOut]
    favorite_count: int
    library_count: int
    recycle_count: int
    storage: WorkspaceStorageOut
    recycle_retention_days: int


class DocumentCreate(InputModel):
    kind: Literal["note", "source"]
    title: str = Field(min_length=1, max_length=200)
    chapter_id: int | None = None
    language: Literal["c", "h"] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned

    @model_validator(mode="after")
    def validate_language(self):
        if self.kind == "note" and self.language is not None:
            raise ValueError("笔记不能设置源码语言")
        if self.kind == "source" and self.language not in ("c", "h"):
            raise ValueError("源码必须设置 c 或 h 语言")
        return self


class DocumentPatch(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    chapter_id: int | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned


class BlockIn(InputModel):
    id: int | None = Field(default=None, gt=0)
    block_type: Literal["rich_text", "code", "remark", "result", "image", "formula"]
    content: dict[str, Any]
    asset_id: int | None = None


class DocumentSaveIn(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    chapter_id: int | None = None
    blocks: list[BlockIn] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned


class BlockOut(BaseModel):
    id: int
    block_type: str
    content: dict[str, Any]
    asset_id: int | None
    sort_order: int


class DocumentSummaryOut(BaseModel):
    id: int
    kind: str
    title: str
    summary: str
    chapter_id: int | None
    chapter_name: str | None
    language: str | None
    visibility: str
    is_favorite: bool
    version: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, value: datetime) -> str:
        return to_iso_utc(value) or ""


class DocumentDetailOut(DocumentSummaryOut):
    share_token: str | None = None
    share_url: str | None = None
    published_at: datetime | None = None
    published_version: int | None = None
    blocks: list[BlockOut]

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime | None) -> str | None:
        return to_iso_utc(value)


class DocumentOrderIn(InputModel):
    document_ids: list[int] = Field(default_factory=list)


class FavoriteCountOut(BaseModel):
    count: int


class VisibilityUpdate(InputModel):
    visibility: Literal["public", "private"]


class PublicationOut(BaseModel):
    visibility: Literal["public", "private"]
    share_token: str | None = None
    share_url: str | None = None
    published_at: datetime | None = None
    published_version: int | None = None

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime | None) -> str | None:
        return to_iso_utc(value)


class PublicAuthorOut(BaseModel):
    display_name: str


class PublicBlockOut(BaseModel):
    block_type: str
    content: dict[str, Any]
    asset_id: int | None
    sort_order: int


class PublicDocumentOut(BaseModel):
    title: str
    kind: str
    language: str | None
    author: PublicAuthorOut
    published_at: datetime
    blocks: list[PublicBlockOut]

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime) -> str:
        return to_iso_utc(value) or ""


class AssetOut(BaseModel):
    id: int
    original_name: str
    mime_type: str
    size_bytes: int


class RecycleOut(BaseModel):
    id: int
    document_id: int
    title: str
    kind: str
    original_chapter_id: int | None
    original_chapter_name: str | None = None
    deleted_at: datetime
    expires_at: datetime
    days_remaining: int

    @field_serializer("deleted_at", "expires_at")
    def serialize_deleted_at(self, value: datetime) -> str:
        return to_iso_utc(value) or ""


class RestoreIn(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned


class AdminSettingsOut(BaseModel):
    registration_enabled: bool


class AdminRegistrationIn(InputModel):
    enabled: bool


class AdminUserStatusIn(InputModel):
    enabled: bool


class AdminQuotaIn(InputModel):
    quota_bytes: int | None = Field(default=None, ge=0)


class AdminUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    is_enabled: bool
    is_admin: bool
    email_verified_at: datetime | None
    created_at: datetime
    storage_quota_bytes: int | None
    effective_quota_bytes: int
    used_bytes: int
    reserved_bytes: int
    document_count: int
    recycle_count: int
    deletion_requested_at: datetime | None
    purge_after: datetime | None

    @field_serializer(
        "email_verified_at",
        "created_at",
        "deletion_requested_at",
        "purge_after",
    )
    def serialize_dt(self, value: datetime | None) -> str | None:
        return to_iso_utc(value)


class AdminUserListOut(BaseModel):
    users: list[AdminUserOut]
    total: int


class AdminPublicDocumentOut(BaseModel):
    document_id: int
    title: str
    owner_user_id: int
    owner_email: str
    author_display_name: str
    published_at: datetime
    source_version: int
    share_url: str | None = None

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime) -> str:
        return to_iso_utc(value) or ""


class AdminPublicListOut(BaseModel):
    documents: list[AdminPublicDocumentOut]


class AdminAuditOut(BaseModel):
    id: int
    action: str
    admin_user_id: int | None
    admin_email: str | None
    target_user_id: int | None
    target_user_email: str | None
    target_document_id: int | None
    target_document_title: str | None
    details: dict[str, Any]
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return to_iso_utc(value) or ""


class AdminAuditListOut(BaseModel):
    entries: list[AdminAuditOut]

from pathlib import Path

from app.config import get_settings


def asset_path(owner_user_id: int, storage_name: str) -> Path:
    settings = get_settings()
    return settings.uploads_path / str(owner_user_id) / storage_name

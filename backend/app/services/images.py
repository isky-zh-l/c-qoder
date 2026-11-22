from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.errors import ApiError

settings = get_settings()

FORMAT_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}
FORMAT_EXTENSION = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "GIF": ".gif",
}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class ImageInfo:
    format: str
    mime_type: str
    extension: str
    width: int
    height: int


def inspect_image(path: Path, size_bytes: int) -> ImageInfo:
    if size_bytes > settings.max_image_bytes:
        raise ApiError(
            413,
            "payload_too_large",
            f"图片不能超过 {settings.max_image_bytes // (1024 * 1024)} MB",
        )
    if size_bytes <= 0:
        raise ApiError(422, "validation_error", "图片文件为空")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                image.verify()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        ValueError,
    ):
        raise ApiError(
            415,
            "unsupported_media_type",
            "文件不是有效的 PNG/JPEG/WebP/GIF 图片",
        )

    if image_format not in FORMAT_MIME:
        raise ApiError(
            415,
            "unsupported_media_type",
            "只允许 PNG/JPEG/WebP/GIF 图片",
        )
    if width <= 0 or height <= 0:
        raise ApiError(422, "validation_error", "图片尺寸无效")
    if (
        width > settings.image_max_dimension
        or height > settings.image_max_dimension
    ):
        raise ApiError(
            413,
            "payload_too_large",
            f"图片宽高不能超过 {settings.image_max_dimension} 像素",
        )
    return ImageInfo(
        format=image_format,
        mime_type=FORMAT_MIME[image_format],
        extension=FORMAT_EXTENSION[image_format],
        width=width,
        height=height,
    )


def safe_original_name(filename: str | None, extension: str) -> str:
    base = Path(filename or "image").name
    base = _CONTROL_CHARS.sub("", base).strip()
    stem = Path(base).stem.strip() or "image"
    stem = stem[:180].rstrip(" .") or "image"
    return f"{stem}{extension}"

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.schemas import BlockIn
from app.services.content import markdown_plain_text
from app.services.documents import create_document

settings = get_settings()
MAX_IMPORT_BLOCKS = 500
ALLOWED_IMPORT_SUFFIXES = {".md", ".c", ".h"}

_FENCE_RE = re.compile(r"^\s*```([A-Za-z0-9_+-]*)\s*$")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_TODO_RE = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.*)$")
_UL_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
_OL_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_HR_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_IMAGE_ONLY_RE = re.compile(
    r"^\s*!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)\s*$"
)
_ASSET_IMAGE_RE = re.compile(r"^/.+/assets/(\d+)/file$")


def _text_module(module: str, markdown: str = "") -> BlockIn:
    content: dict[str, Any] = {"module": module}
    if module != "divider":
        content["markdown"] = markdown
    return BlockIn(
        block_type="rich_text",
        content=content,
        asset_id=None,
    )


def _split_table_row(line: str) -> list[str]:
    cleaned = line.strip()
    if cleaned.startswith("|"):
        cleaned = cleaned[1:]
    if cleaned.endswith("|"):
        cleaned = cleaned[:-1]
    return [cell.strip() for cell in cleaned.split("|")]


def _is_block_start(lines: list[str], index: int) -> bool:
    line = lines[index]
    stripped = line.strip()
    return bool(
        _FENCE_RE.match(line)
        or _HEADING_RE.match(line)
        or _HR_RE.match(line)
        or _QUOTE_RE.match(line)
        or _TODO_RE.match(line)
        or _UL_RE.match(line)
        or _OL_RE.match(line)
        or _IMAGE_ONLY_RE.match(line)
        or stripped == "$$"
        or (
            "|" in line
            and index + 1 < len(lines)
            and _TABLE_SEPARATOR_RE.match(lines[index + 1])
        )
    )


def _parse_table(lines: list[str], index: int) -> tuple[BlockIn, int]:
    headers = _split_table_row(lines[index])
    rows: list[list[str]] = []
    cursor = index + 2
    while cursor < len(lines) and "|" in lines[cursor] and lines[cursor].strip():
        rows.append(_split_table_row(lines[cursor]))
        cursor += 1
    width = len(headers)
    normalized_rows = [
        (row + [""] * width)[:width]
        for row in rows
    ]
    return (
        BlockIn(
            block_type="rich_text",
            content={
                "module": "table",
                "headers": headers,
                "rows": normalized_rows,
            },
            asset_id=None,
        ),
        cursor,
    )


def markdown_blocks(source: str) -> tuple[list[BlockIn], str | None]:
    blocks: list[BlockIn] = []
    first_h1: str | None = None
    lines = source.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            language = fence.group(1).lower()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and _FENCE_RE.match(lines[index]) is None:
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(
                BlockIn(
                    block_type="code",
                    content={
                        "text": "\n".join(code_lines),
                        "language": language if language in ("c", "h") else "text",
                    },
                    asset_id=None,
                )
            )
            continue

        if stripped == "$$":
            latex_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "$$":
                latex_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(
                BlockIn(
                    block_type="formula",
                    content={"latex": "\n".join(latex_lines).strip()},
                    asset_id=None,
                )
            )
            continue
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            blocks.append(
                BlockIn(
                    block_type="formula",
                    content={"latex": stripped[2:-2].strip()},
                    asset_id=None,
                )
            )
            index += 1
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = min(len(heading.group(1)), 3)
            heading_text = heading.group(2).strip()
            if level == 1 and first_h1 is None:
                first_h1 = markdown_plain_text(heading_text) or heading_text
            blocks.append(_text_module(f"heading{level}", heading_text))
            index += 1
            continue

        if _HR_RE.match(line):
            blocks.append(_text_module("divider"))
            index += 1
            continue

        if (
            "|" in line
            and index + 1 < len(lines)
            and _TABLE_SEPARATOR_RE.match(lines[index + 1])
        ):
            table, index = _parse_table(lines, index)
            blocks.append(table)
            continue

        quote = _QUOTE_RE.match(line)
        if quote:
            values: list[str] = []
            while index < len(lines):
                current = _QUOTE_RE.match(lines[index])
                if not current:
                    break
                values.append(current.group(1))
                index += 1
            blocks.append(_text_module("quote", "\n".join(values)))
            continue

        if _TODO_RE.match(line):
            list_lines: list[str] = []
            while index < len(lines) and _TODO_RE.match(lines[index]):
                list_lines.append(lines[index].strip())
                index += 1
            blocks.append(_text_module("todo_list", "\n".join(list_lines)))
            continue

        if _UL_RE.match(line):
            list_lines = []
            while index < len(lines) and _UL_RE.match(lines[index]):
                if _TODO_RE.match(lines[index]):
                    break
                list_lines.append(lines[index].strip())
                index += 1
            blocks.append(_text_module("bullet_list", "\n".join(list_lines)))
            continue

        if _OL_RE.match(line):
            list_lines = []
            while index < len(lines) and _OL_RE.match(lines[index]):
                list_lines.append(lines[index].strip())
                index += 1
            blocks.append(_text_module("ordered_list", "\n".join(list_lines)))
            continue

        image = _IMAGE_ONLY_RE.match(line)
        if image:
            alt, target, caption = image.groups()
            asset_match = _ASSET_IMAGE_RE.match(target)
            if asset_match:
                blocks.append(
                    BlockIn(
                        block_type="image",
                        content={"alt": alt, "caption": caption or ""},
                        asset_id=int(asset_match.group(1)),
                    )
                )
            else:
                blocks.append(
                    _text_module(
                        "paragraph",
                        alt or "外部图片未导入",
                    )
                )
            index += 1
            continue

        paragraph_lines = [line.rstrip()]
        index += 1
        while index < len(lines) and lines[index].strip():
            if _is_block_start(lines, index):
                break
            paragraph_lines.append(lines[index].rstrip())
            index += 1
        blocks.append(_text_module("paragraph", "\n".join(paragraph_lines)))

    if len(blocks) > MAX_IMPORT_BLOCKS:
        raise ApiError(413, "payload_too_large", "导入后的模块数量超过上限")
    return blocks, first_h1


def import_document(
    db: Session,
    user_id: int,
    *,
    filename: str,
    contents: bytes,
    title: str | None,
    chapter_id: int | None,
):
    safe_name = Path(filename or "").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_IMPORT_SUFFIXES:
        raise ApiError(
            415,
            "unsupported_media_type",
            "只允许上传 .md、.c 或 .h 文件",
        )
    if len(contents) > settings.max_file_bytes:
        raise ApiError(
            413,
            "payload_too_large",
            f"导入文件不能超过 {settings.max_file_bytes // (1024 * 1024)} MB",
        )
    if not contents.strip():
        raise ApiError(422, "validation_error", "导入文件为空")
    try:
        source = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(422, "validation_error", "导入文件必须是 UTF-8 文本")

    stem = Path(safe_name).stem.strip() or "导入文档"
    if suffix == ".md":
        blocks, heading_title = markdown_blocks(source)
        final_title = (title or "").strip() or heading_title or stem
        return create_document(
            db,
            user_id,
            kind="note",
            title=final_title,
            chapter_id=chapter_id,
            language=None,
            blocks=blocks,
        )

    language = suffix.lstrip(".")
    return create_document(
        db,
        user_id,
        kind="source",
        title=(title or "").strip() or stem,
        chapter_id=chapter_id,
        language=language,
        blocks=[
            BlockIn(
                block_type="code",
                content={"text": source, "language": language},
                asset_id=None,
            )
        ],
    )

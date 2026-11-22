from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

from app.errors import ApiError

TEXT_MODULES = {
    "paragraph",
    "heading1",
    "heading2",
    "heading3",
    "quote",
    "divider",
    "bullet_list",
    "ordered_list",
    "todo_list",
    "table",
}
HIGHLIGHT_TONES = {"yellow", "purple", "mint", "pink"}
MAX_MARKDOWN_CHARS = 200_000
MAX_TABLE_COLUMNS = 20
MAX_TABLE_ROWS = 100
MAX_TABLE_CELLS = 500
MAX_BLOCK_FORMULA = 4000

_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9:-]*)((?:\s+[^<>]*?)?)\s*/?>")
_MARK_OPEN_RE = re.compile(
    r'^<mark\s+data-tone="(yellow|purple|mint|pink)"\s*>$'
)
_PROTECTED_RE = re.compile(
    r"```[\s\S]*?```|`[^`\n]*`|\$\$[\s\S]*?\$\$|\$[^$\n]+\$"
)
_LINK_RE = re.compile(
    r"(!?)\[([^\]\n]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)"
)


def _error(message: str) -> None:
    raise ApiError(422, "validation_error", message)


def _mask_protected(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        return "".join("\n" if char == "\n" else " " for char in value)

    return _PROTECTED_RE.sub(replace, text)


def _safe_link(target: str, *, image: bool) -> bool:
    cleaned = html.unescape(target).strip()
    if not cleaned or any(ord(char) < 32 for char in cleaned):
        return False
    if image:
        return bool(re.match(r"^/.+/assets/\d+/file$", cleaned))
    if cleaned.startswith("/") and not cleaned.startswith("//"):
        return True
    parsed = urlparse(cleaned)
    return parsed.scheme.lower() in {"http", "https", "mailto"}


def validate_markdown(value: str, label: str = "Markdown") -> str:
    if not isinstance(value, str):
        _error(f"{label} 必须是文本")
    if len(value) > MAX_MARKDOWN_CHARS:
        _error(f"{label} 超过长度限制")
    masked = _mask_protected(value)

    for match in _TAG_RE.finditer(masked):
        token = match.group(0)
        if token in {"<u>", "</u>", "</mark>"}:
            continue
        if _MARK_OPEN_RE.match(token):
            continue
        _error("只允许 <u> 和四种 mark data-tone 标签")

    for match in _LINK_RE.finditer(masked):
        is_image = match.group(1) == "!"
        target = match.group(3)
        if len(target) > 2048:
            _error("链接地址超过 2048 字符")
        if not _safe_link(target, image=is_image):
            kind = "图片" if is_image else "链接"
            _error(f"{kind}地址不在允许范围内")
    return value


def validate_rich_text_content(content: dict[str, Any], *, kind: str) -> None:
    module = content.get("module")
    if module is None:
        # 旧笔记继续可读；新版编辑器保存时统一转成 module 格式。
        return
    if kind != "note":
        _error("源码文档不能使用笔记文本模块")
    if module not in TEXT_MODULES:
        _error("未知的文本模块类型")

    if module == "divider":
        return
    if module == "table":
        headers = content.get("headers")
        rows = content.get("rows")
        if not isinstance(headers, list) or not isinstance(rows, list):
            _error("表格缺少 headers 或 rows")
        if not headers or len(headers) > MAX_TABLE_COLUMNS:
            _error("表格列数不合法")
        if len(rows) > MAX_TABLE_ROWS:
            _error("表格行数超过限制")
        if (len(rows) + 1) * len(headers) > MAX_TABLE_CELLS:
            _error("表格单元格数量超过限制")
        for cell in headers:
            if not isinstance(cell, str):
                _error("表格单元格必须是文本")
            validate_markdown(cell, "表格单元格")
        for row in rows:
            if not isinstance(row, list) or len(row) != len(headers):
                _error("表格行列不一致")
            for cell in row:
                if not isinstance(cell, str):
                    _error("表格单元格必须是文本")
                validate_markdown(cell, "表格单元格")
        return

    markdown = content.get("markdown")
    if not isinstance(markdown, str):
        _error("文本模块缺少 markdown")
    validate_markdown(markdown)
    if module in {"heading1", "heading2", "heading3"} and "\n" in markdown.strip():
        _error("标题模块只能包含一行")


def validate_code_content(content: dict[str, Any]) -> None:
    text = content.get("text")
    language = content.get("language")
    if not isinstance(text, str):
        _error("代码模块缺少文本")
    if len(text) > 200_000:
        _error("代码模块超过长度限制")
    if language not in {"c", "h", "text"}:
        _error("代码语言只允许 c、h 或 text")


def validate_formula_content(content: dict[str, Any]) -> None:
    latex = content.get("latex")
    if not isinstance(latex, str) or not latex.strip():
        _error("公式模块缺少 latex")
    if len(latex) > MAX_BLOCK_FORMULA:
        _error("公式超过长度限制")


def validate_image_content(content: dict[str, Any]) -> None:
    alt = content.get("alt", "")
    caption = content.get("caption", "")
    if not isinstance(alt, str) or len(alt) > 1000:
        _error("图片替代文本不合法")
    if not isinstance(caption, str) or len(caption) > 2000:
        _error("图片说明不合法")


def markdown_plain_text(value: str) -> str:
    text = _mask_protected(value)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"</?u>", "", text)
    text = re.sub(r'</?mark(?:\s+data-tone="[^"]+")?>', "", text)
    text = re.sub(r"(``|`|\*\*|~~|==)", "", text)
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s?|\[[ xX]\]\s+)+", "", text, flags=re.M)
    return " ".join(text.split())


def markdown_asset_ids(value: str) -> set[int]:
    return {
        int(match.group(1))
        for match in re.finditer(r"/assets/(\d+)/file", value)
        if match.group(1).isdigit()
    }


def block_asset_ids(
    block_type: str,
    content: dict[str, Any],
    asset_id: int | None,
) -> set[int]:
    ids: set[int] = set()
    if asset_id is not None:
        ids.add(asset_id)
    if block_type in ("rich_text", "remark"):
        ids.update(rich_content_asset_ids(content))
    return ids


def rich_content_asset_ids(content: dict[str, Any]) -> set[int]:
    module = content.get("module")
    if module == "table":
        values: list[str] = []
        for cell in content.get("headers", []):
            if isinstance(cell, str):
                values.append(cell)
        for row in content.get("rows", []):
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, str):
                        values.append(cell)
        result: set[int] = set()
        for value in values:
            result.update(markdown_asset_ids(value))
        return result
    markdown = content.get("markdown")
    return markdown_asset_ids(markdown) if isinstance(markdown, str) else set()


def rich_content_plain_text(content: dict[str, Any]) -> str:
    module = content.get("module")
    if module in TEXT_MODULES:
        if module == "divider":
            return ""
        if module == "table":
            values: list[str] = []
            for cell in content.get("headers", []):
                if isinstance(cell, str):
                    values.append(markdown_plain_text(cell))
            for row in content.get("rows", []):
                if isinstance(row, list):
                    for cell in row:
                        if isinstance(cell, str):
                            values.append(markdown_plain_text(cell))
            return " ".join(values)
        value = content.get("markdown")
        return markdown_plain_text(value) if isinstance(value, str) else ""
    return ""

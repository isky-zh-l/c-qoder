from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Block, Document


def join_source_code(parts: list[str]) -> str:
    result = ""
    for code in parts:
        if code == "":
            continue
        if result and not result.endswith(("\n", "\r")):
            result += "\n"
        result += code
    return result


def source_code(db: Session, document: Document) -> str:
    blocks = db.scalars(
        select(Block)
        .where(
            Block.document_id == document.id,
            Block.block_type == "code",
        )
        .order_by(Block.sort_order, Block.id)
    ).all()
    parts = [
        block.content.get("text", "")
        for block in blocks
        if isinstance(block.content.get("text"), str)
    ]
    return join_source_code(parts)


def source_filename(document: Document) -> str:
    title = re.sub(r'[\\/:*?"<>|\r\n]+', "-", document.title).strip()
    title = title or "source"
    extension = document.language if document.language in ("c", "h") else "txt"
    return f"{title}.{extension}"

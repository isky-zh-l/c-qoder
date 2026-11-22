from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, User
from app.security import utcnow

DEFAULT_CHAPTERS = (
    "起步与工具链",
    "变量与基本类型",
    "运算符与表达式",
    "分支与循环",
    "函数与作用域",
    "数组与字符串",
    "指针与内存",
    "结构体与联合体",
    "动态内存",
    "文件与 I/O",
    "预处理器与多文件",
    "调试与常见错误",
)


def initialize_user_workspace(db: Session, user_id: int) -> None:
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one()
    if user.workspace_initialized_at is not None:
        return

    existing = set(
        db.scalars(
            select(Chapter.name).where(Chapter.owner_user_id == user_id)
        ).all()
    )
    next_order = len(existing)
    for name in DEFAULT_CHAPTERS:
        if name in existing:
            continue
        db.add(
            Chapter(
                owner_user_id=user_id,
                name=name,
                sort_order=next_order,
            )
        )
        next_order += 1

    user.workspace_initialized_at = utcnow()
    db.flush()

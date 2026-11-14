"""把一个已注册用户设为管理员（审核内容、处理举报需要）。

用法（项目根目录）：
    python -m app.make_admin you@example.com
加 --revoke 取消管理员。
"""
import sys

from sqlalchemy import select

from app.core.db import get_db
from app.models import User


def main(argv: list[str]) -> int:
    revoke = "--revoke" in argv
    emails = [item.strip().lower() for item in argv if not item.startswith("--")]
    if len(emails) != 1:
        print("用法: python -m app.make_admin <邮箱> [--revoke]")
        return 2
    session = next(get_db())
    try:
        user = session.scalar(select(User).where(User.email == emails[0], User.deleted_at.is_(None)))
        if user is None:
            print(f"找不到用户 {emails[0]}")
            return 1
        user.is_admin = not revoke
        session.commit()
        print(f"{user.email}: is_admin = {user.is_admin}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

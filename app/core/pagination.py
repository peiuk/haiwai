import base64
from datetime import datetime
from typing import TypeVar

T = TypeVar("T")


def encode_cursor(*parts: str) -> str:
    raw = "\x1f".join(parts)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> list[str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    parts = raw.split("\x1f")
    return parts if parts else None


def parse_added_at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def paginate_rows(
    rows: list[T],
    cursor: str | None,
    limit: int,
    id_attr: str,
    at_attr: str,
) -> tuple[list[T], str | None]:
    """通用游标分页：按 (id, at) 定位已消费位置，返回本页与 next_cursor。

    游标由两段组成：`id_attr` 对应的标识符与 `at_attr` 对应的 ISO 时间戳。
    rows 需已按时间倒序排好；游标无效时从第一页开始，不做报错。
    """
    start = 0
    if cursor:
        parts = decode_cursor(cursor)
        if parts and len(parts) == 2:
            cursor_id, cursor_at = parts[0], parts[1]
            for index, row in enumerate(rows):
                row_at = getattr(row, at_attr)
                if getattr(row, id_attr) == cursor_id and (
                    row_at.isoformat() if isinstance(row_at, datetime) else str(row_at)
                ) == cursor_at:
                    start = index + 1
                    break
    page = rows[start : start + limit]
    next_cursor = None
    if start + limit < len(rows) and page:
        last = page[-1]
        last_at = getattr(last, at_attr)
        next_cursor = encode_cursor(
            str(getattr(last, id_attr)),
            last_at.isoformat() if isinstance(last_at, datetime) else str(last_at),
        )
    return page, next_cursor

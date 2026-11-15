import time
from collections import deque
from contextvars import ContextVar

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog

# 当前请求的（来源 IP，浏览器标识）。main.py 的中间件在每个请求开始时设置，write_audit 读取，
# 这样几十个调用点都不用多传参数。
request_meta: ContextVar[tuple[str | None, str | None]] = ContextVar("request_meta", default=(None, None))


def client_ip(request: Request) -> str | None:
    """请求的来源 IP。在反向代理后面（TRUST_PROXY=true）取代理记下的地址，否则取直接连接的对端。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and get_settings().trust_proxy:
        # 代理把它看到的对端追加在最右边；左边的是客户端自己能随便写的，不能信
        return forwarded.split(",")[-1].strip()[:64] or None
    return request.client.host if request.client else None


def write_audit(
    session: Session,
    actor_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
) -> None:
    ip, agent = request_meta.get()
    session.add(
        AuditLog(
            actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, detail=detail, ip=ip, user_agent=agent
        )
    )


# shortcut: 服务器错误次数记在每个进程的内存里，多个 worker 各算各的、重启清零；
# 要准确的告警请接外部监控（见 README 的「备份与监控」）。
_errors: deque[float] = deque(maxlen=1000)


def note_server_error() -> None:
    _errors.append(time.monotonic())


def recent_server_errors(window_seconds: int = 3600) -> int:
    now = time.monotonic()
    return sum(1 for at in _errors if now - at <= window_seconds)

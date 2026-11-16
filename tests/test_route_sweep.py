"""全接口扫一遍：随便给的 id、空请求体、乱填的请求体，不论游客 / 用户 / 管理员，都不能 500。"""
import re

from app.models import Channel, ChannelItem, Content
from tests.test_admin import headers, register, user_id

JUNK_BODIES = [None, {}, {"title": "x" * 5000, "body": 123, "items": "nope", "user_id": None}, []]


def _seed(client) -> dict[str, str]:
    """准备一套真实 id：频道、房间、帖子、用户，让接口能走到 404 之后的逻辑。"""
    author = user_id(client, "sweep-user@example.com")
    with client.session_factory() as session:
        channel = Channel(code="sweep-ch", name_hans="扫描", name_hant="掃描", kind="official_curated", region_code="GLOBAL", is_active=True)
        session.add(channel)
        session.flush()
        room = Channel(code="sweep-room", name_hans="房间", name_hant="房間", kind="room", region_code="GLOBAL",
                       is_active=True, owner_id=author, parent_channel_id=channel.id)
        content = Content(type="post", status="published", author_id=author, title="扫描帖", summary="正文", body="正文")
        session.add_all([room, content])
        session.flush()
        session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
        session.commit()
        return {"channel": channel.id, "room": room.id, "content": content.id, "user": author}


def _fill(path: str, real: dict[str, str] | None) -> str:
    def value(match: re.Match) -> str:
        name = match.group(1)
        if real is None:
            return "does-not-exist"
        for key, val in real.items():
            if key in name:
                return val
        if name in {"channel_id", "room_id", "id"}:
            return real["room"]
        return real["content"] if "content" in name or name == "item_id" else "does-not-exist"
    return re.sub(r"\{([^}:]+)(?::[^}]*)?\}", value, path)


def test_no_route_returns_500_on_bad_input(client):
    user = register(client, "sweep-user@example.com")
    admin = register(client, "sweep-admin@example.com", admin=True)
    real = _seed(client)
    roles = {"guest": {}, "user": headers(user), "admin": headers(admin)}
    failures: list[str] = []
    routes = {path: ops for path, ops in client.app.openapi()["paths"].items() if path.startswith("/api/")}
    assert len(routes) > 100
    for route_path, ops in routes.items():
        for method in (m.upper() for m in ops):
            if method == "DELETE" and route_path.endswith("/me") or route_path.endswith("/logout"):
                continue  # 注销 / 退出会让后面的请求全变成 401，扫不到东西
            for ids in (None, real):
                path = _fill(route_path, ids)
                for role, auth in roles.items():
                    for body in JUNK_BODIES if method in {"POST", "PUT", "PATCH"} else [None]:
                        try:
                            response = client.request(method, path, headers=auth, json=body)
                        except Exception as exc:  # noqa: BLE001 - 扫描就是要把异常记下来
                            failures.append(f"{method} {path} [{role}] body={body!r:.40} -> {type(exc).__name__}: {exc}"[:300])
                            continue
                        if response.status_code == 500:  # 503 是有意的「服务未就绪 / 未配置」
                            failures.append(f"{method} {path} [{role}] body={body!r:.40} -> {response.status_code}")
    assert failures == [], "\n".join(failures)

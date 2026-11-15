"""管理后台：只有管理员能进，写操作都留审计。"""
from sqlalchemy import select

from app.models import AuditLog, Channel, Content, ModerationCase, RoomComment, User

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str, admin: bool = False) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": email.split("@")[0], "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    if admin:
        with client.session_factory() as session:
            session.scalar(select(User).where(User.email == email)).is_admin = True
            session.commit()
    return response.json()["access_token"]


def user_id(client, email: str) -> str:
    with client.session_factory() as session:
        return session.scalar(select(User.id).where(User.email == email))


def seed(client, author_email: str, status: str = "published") -> tuple[str, str]:
    """一个频道 + 一条帖子，返回 (channel_id, content_id)。"""
    with client.session_factory() as session:
        channel = Channel(code="uk-admin", name_hans="后台测试", name_hant="後台測試", kind="official_curated", is_active=True)
        content = Content(type="post", status=status, title="后台测试帖", body="正文", author_id=user_id(client, author_email))
        session.add_all([channel, content])
        session.commit()
        return channel.id, content.id


def audit_actions(client) -> list[str]:
    with client.session_factory() as session:
        rows = session.scalars(select(AuditLog.action).order_by(AuditLog.created_at))
        return [row for row in rows if not row.startswith("account.") and row != "admin.login"]  # 注册本身也记审计，这里只看后台动作


def test_me_reports_admin_flag(client):
    token = register(client, "plain@example.com")
    assert client.get("/api/v1/me", headers=headers(token)).json()["is_admin"] is False
    boss = register(client, "boss@example.com", admin=True)
    assert client.get("/api/v1/me", headers=headers(boss)).json()["is_admin"] is True


def test_admin_endpoints_reject_non_admin(client):
    token = register(client, "plain@example.com")
    calls = [
        ("get", "/api/v1/admin/stats", None),
        ("get", "/api/v1/admin/queue", None),
        ("get", "/api/v1/admin/users", None),
        ("get", "/api/v1/admin/contents", None),
        ("get", "/api/v1/admin/channels", None),
        ("get", "/api/v1/admin/comments", None),
        ("post", "/api/v1/admin/comments/x/status", {"action": "remove"}),
        ("get", "/api/v1/admin/audit", None),
        ("post", "/api/v1/admin/users/x/status", {"status": "suspended"}),
        ("post", "/api/v1/admin/contents/x/status", {"action": "remove"}),
        ("post", "/api/v1/admin/channels/x/active", {"active": False}),
    ]
    for method, url, body in calls:
        kwargs = {"json": body} if body else {}
        assert getattr(client, method)(url, headers=headers(token), **kwargs).status_code == 403, url
        assert getattr(client, method)(url, **kwargs).status_code == 401, url
    assert audit_actions(client) == []


def test_moderation_decision_writes_audit(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com", status="pending")
    done = client.post(f"/api/v1/moderation/{content_id}/decision", headers=headers(boss), json={"decision": "approve"})
    assert done.status_code == 200, done.text
    assert audit_actions(client) == ["moderation.approve"]


def test_suspend_and_reactivate_user(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "boss2@example.com", admin=True)
    victim = register(client, "victim@example.com")
    victim_id = user_id(client, "victim@example.com")
    url = f"/api/v1/admin/users/{victim_id}/status"

    listed = client.get("/api/v1/admin/users?q=victim", headers=headers(boss)).json()["items"]
    assert [row["email"] for row in listed] == ["victim@example.com"]

    assert client.post(url, headers=headers(boss), json={"status": "suspended"}).status_code == 200
    assert client.get("/api/v1/me", headers=headers(victim)).status_code == 401  # 旧 token 立刻失效
    assert client.post(url, headers=headers(boss), json={"status": "suspended"}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"status": "active"}).status_code == 200
    assert client.get("/api/v1/me", headers=headers(victim)).status_code == 200

    for email in ("boss@example.com", "boss2@example.com"):  # 自己和其他管理员都不能封
        denied = client.post(f"/api/v1/admin/users/{user_id(client, email)}/status", headers=headers(boss), json={"status": "suspended"})
        assert denied.status_code == 409, denied.text
    assert audit_actions(client) == ["admin.user.suspend", "admin.user.activate"]


def test_remove_and_restore_content(client):
    boss = register(client, "boss@example.com", admin=True)
    author = register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")
    url = f"/api/v1/admin/contents/{content_id}/status"

    assert client.post(url, headers=headers(boss), json={"action": "restore"}).status_code == 409  # 没下架过
    assert client.post(url, headers=headers(boss), json={"action": "remove"}).status_code == 200
    assert client.get(f"/api/v1/contents/{content_id}").status_code == 404
    found = client.get("/api/v1/admin/contents?status=deleted", headers=headers(boss)).json()["items"]
    assert [row["content_id"] for row in found] == [content_id]
    assert client.post(url, headers=headers(boss), json={"action": "remove"}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"action": "restore"}).status_code == 200
    assert client.get(f"/api/v1/contents/{content_id}").status_code == 200
    assert audit_actions(client) == ["admin.content.remove", "admin.content.restore"]

    # 作者自己删的帖子，后台不能复活
    assert client.delete(f"/api/v1/contents/{content_id}", headers=headers(author)).status_code == 200
    with client.session_factory() as session:
        session.query(AuditLog).delete()
        session.commit()
    assert client.post(url, headers=headers(boss), json={"action": "restore"}).status_code == 409


def test_queue_and_stats(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com", status="pending")
    with client.session_factory() as session:
        session.add(ModerationCase(reported_user_id=user_id(client, "author@example.com"), reason="spam", detail="刷屏"))
        session.commit()

    queue = client.get("/api/v1/admin/queue", headers=headers(boss)).json()
    assert [row["content_id"] for row in queue["contents"]] == [content_id]
    assert queue["contents"][0]["author_name"] == "author"
    assert [(row["target_type"], row["target_label"], row["reason"]) for row in queue["cases"]] == [("user", "author", "spam")]
    assert queue["comments"] == [] and queue["channels"] == []

    stats = client.get("/api/v1/admin/stats", headers=headers(boss)).json()
    trend = stats.pop("trend")
    assert len(trend) == 14 and trend[-1]["posts"] == 1 and trend[-1]["users"] == 2
    assert sum(day["posts"] for day in trend) == 1
    assert stats == {
        "total_users": 2,
        "total_contents": 0,
        "new_posts_today": 1,
        "new_users_today": 2,
        "pending_contents": 1,
        "pending_comments": 0,
        "pending_channels": 0,
        "open_cases": 1,
    }


def test_channel_toggle_and_audit_list(client):
    boss = register(client, "boss@example.com", admin=True)
    channel_id, _ = seed(client, "boss@example.com")
    url = f"/api/v1/admin/channels/{channel_id}/active"

    assert client.post(url, headers=headers(boss), json={"active": True}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"active": False}).status_code == 200
    listed = client.get("/api/v1/admin/channels?q=uk-admin", headers=headers(boss)).json()["items"]
    assert [(row["channel_id"], row["is_active"]) for row in listed] == [(channel_id, False)]
    assert client.post(url, headers=headers(boss), json={"active": True}).status_code == 200

    audit = client.get("/api/v1/admin/audit?action=admin.", headers=headers(boss)).json()
    assert [row["action"] for row in audit["items"]] == ["admin.channel.activate", "admin.channel.deactivate"]
    assert audit["items"][0]["actor_name"] == "boss" and audit["items"][0]["target_id"] == channel_id
    assert audit["next_cursor"] is None
    only = client.get("/api/v1/admin/audit?action=deactivate", headers=headers(boss)).json()["items"]
    assert [row["action"] for row in only] == ["admin.channel.deactivate"]


def test_admin_login_only_for_admins(client):
    register(client, "boss@example.com", admin=True)
    register(client, "plain@example.com")
    url = "/api/v1/admin/login"
    assert client.post(url, json={"email": "boss@example.com", "password": "wrong-pass"}).status_code == 401
    denied = client.post(url, json={"email": "plain@example.com", "password": "password-1"})
    assert denied.status_code == 403 and "access_token" not in denied.json()
    ok = client.post(url, json={"email": "boss@example.com", "password": "password-1"})
    assert ok.status_code == 200, ok.text
    assert client.get("/api/v1/admin/stats", headers=headers(ok.json()["access_token"])).status_code == 200
    with client.session_factory() as session:
        assert session.scalar(select(AuditLog.action).where(AuditLog.action == "admin.login")) == "admin.login"


def test_remove_and_restore_comment(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    channel_id, content_id = seed(client, "author@example.com")
    with client.session_factory() as session:
        mine = RoomComment(room_id=channel_id, content_id=content_id, author_id=user_id(client, "author@example.com"), body="一条留言", status="published")
        gone = RoomComment(room_id=channel_id, author_id=user_id(client, "author@example.com"), body="作者自己删的", status="removed")
        session.add_all([mine, gone])
        session.commit()
        mine_id, gone_id = mine.id, gone.id

    listed = client.get("/api/v1/admin/comments?q=一条", headers=headers(boss)).json()
    assert listed["total"] == 1
    assert [(row["comment_id"], row["room_name"], row["author_name"]) for row in listed["items"]] == [(mine_id, "后台测试", "author")]

    url = f"/api/v1/admin/comments/{mine_id}/status"
    assert client.post(url, headers=headers(boss), json={"action": "restore"}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"action": "remove"}).status_code == 200
    assert client.post(url, headers=headers(boss), json={"action": "remove"}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"action": "restore"}).status_code == 200
    # 作者自己删的留言，后台不能复活
    assert client.post(f"/api/v1/admin/comments/{gone_id}/status", headers=headers(boss), json={"action": "restore"}).status_code == 409
    assert audit_actions(client) == ["admin.comment.remove", "admin.comment.restore"]


def test_lists_paginate_and_filter_by_type(client):
    boss = register(client, "boss@example.com", admin=True)
    with client.session_factory() as session:
        channel = Channel(code="uk-page", name_hans="分页", name_hant="分頁", kind="official_curated", is_active=True)
        session.add(channel)
        session.flush()
        for index in range(23):
            session.add(Content(type="post", status="published", title=f"帖子 {index}", author_id=user_id(client, "boss@example.com")))
        session.add(Content(type="announcement", status="published", title="公告"))
        session.commit()

    first = client.get("/api/v1/admin/contents?type=post", headers=headers(boss)).json()
    assert (first["total"], first["page_size"], len(first["items"])) == (23, 20, 20)
    second = client.get("/api/v1/admin/contents?type=post&page=2", headers=headers(boss)).json()
    assert len(second["items"]) == 3
    assert not {row["content_id"] for row in first["items"]} & {row["content_id"] for row in second["items"]}
    other = client.get("/api/v1/admin/contents?type=news,announcement,topic", headers=headers(boss)).json()
    assert [row["title"] for row in other["items"]] == ["公告"]
    users = client.get("/api/v1/admin/users", headers=headers(boss)).json()
    assert users["total"] == 1 and users["items"][0]["post_count"] == 23

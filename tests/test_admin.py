"""管理后台：只有管理员能进，写操作都留审计。"""
from sqlalchemy import func, select

from app.models import (
    AuditLog,
    Channel,
    ChannelItem,
    ChannelSubscription,
    Content,
    ContentReaction,
    ModerationCase,
    Notification,
    RegionOpenRequest,
    RoomComment,
    UploadObject,
    User,
    UserRegionPref,
    utcnow,
)

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
            user = session.scalar(select(User).where(User.email == email))
            user.is_admin = True
            user.is_super = True
            session.commit()
        return admin_login(client, email)
    return response.json()["access_token"]


def admin_login(client, email: str, code: str = "") -> str:
    """后台接口只认后台登录发的令牌（前台登录没过两步验证）。"""
    response = client.post("/api/v1/admin/login", json={"email": email, "password": "password-1", "code": code})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def user_id(client, email: str) -> str:
    with client.session_factory() as session:
        return session.scalar(select(User.id).where(User.email == email))


def seed(client, author_email: str, status: str = "published") -> tuple[str, str]:
    """一个频道 + 一条帖子，返回 (channel_id, content_id)。"""
    with client.session_factory() as session:
        channel = Channel(code="uk-admin", name_hans="后台测试", name_hant="後台測試", kind="official_curated", is_active=True)
        content = Content(
            type="post",
            status=status,
            title="后台测试帖",
            body="正文",
            author_id=user_id(client, author_email),
            published_at=utcnow() if status == "published" else None,  # 和真实发布路径一致：发布时一定带发布时间
        )
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
        ("get", "/api/v1/admin/users/x", None),
        ("get", "/api/v1/admin/contents/x", None),
        ("get", "/api/v1/admin/channel-options", None),
        ("post", "/api/v1/admin/users/x/admin", {"is_admin": True}),
        ("post", "/api/v1/admin/contents/x/featured", {"featured": True}),
        ("post", "/api/v1/admin/channels/x/certified", {"certified": True}),
        ("post", "/api/v1/admin/announcements", {"title": "公告", "body": "内容内容", "channel_id": "x"}),
        ("get", "/api/v1/admin/regions", None),
        ("post", "/api/v1/admin/regions", {"code": "US", "name": "美国"}),
        ("post", "/api/v1/admin/regions/UK/open", {"open": False}),
        ("post", "/api/v1/admin/regions/UK/channels", None),
        ("post", "/api/v1/admin/channels", {"code": "uk-food", "name_hans": "英国美食", "region_code": "UK"}),
        ("patch", "/api/v1/admin/channels/x", {"name_hans": "改名", "region_code": "UK"}),
        ("post", "/api/v1/admin/channels/x/delete", {"reason": ""}),
        ("post", "/api/v1/admin/contents/x/delete", {"reason": ""}),
        ("post", "/api/v1/admin/users/x/reset-link", None),
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
    relogin = client.post("/api/v1/auth/login", json={"email": "victim@example.com", "password": "password-1"})
    assert relogin.status_code == 403 and relogin.json()["code"] == "ACCOUNT_SUSPENDED"  # 也不能重新登录
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
    want = {
        "total_users": 2,
        "total_contents": 0,
        "new_posts_today": 1,
        "new_users_today": 2,
        "pending_contents": 1,
        "pending_comments": 0,
        "pending_channels": 0,
        "open_cases": 1,
    }
    assert {key: stats[key] for key in want} == want  # 其余是运营指标，另有用例


def test_channel_toggle_and_audit_list(client):
    boss = register(client, "boss@example.com", admin=True)
    channel_id, _ = seed(client, "boss@example.com")
    url = f"/api/v1/admin/channels/{channel_id}/active"

    assert client.post(url, headers=headers(boss), json={"active": True}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"active": False}).status_code == 200
    listed = client.get("/api/v1/admin/channels?q=uk-admin", headers=headers(boss)).json()["items"]
    assert [(row["channel_id"], row["is_active"]) for row in listed] == [(channel_id, False)]
    assert client.post(url, headers=headers(boss), json={"active": True}).status_code == 200

    audit = client.get("/api/v1/admin/audit?action=admin.channel", headers=headers(boss)).json()
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


def test_dev_sqlite_relaxes_stale_not_null(tmp_path):
    """旧开发库的 moderation_case.content_id 必填，启动时要按模型重建，旧数据保留。"""
    from sqlalchemy import create_engine, text

    from app.core.db import _relax_stale_not_null
    from app.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE moderation_case"))
        conn.execute(
            text(
                "CREATE TABLE moderation_case (id VARCHAR(36) PRIMARY KEY, content_id VARCHAR(36) NOT NULL,"
                " reporter_id VARCHAR(36) NOT NULL, reason VARCHAR(32) NOT NULL, status VARCHAR(16) NOT NULL,"
                " decision VARCHAR(24), created_at DATETIME NOT NULL, decided_at DATETIME, reported_user_id VARCHAR(36),"
                " reported_channel_id VARCHAR(36), reported_comment_id VARCHAR(36), detail VARCHAR(300) NOT NULL DEFAULT '')"
            )
        )
        conn.execute(text("INSERT INTO moderation_case (id, content_id, reporter_id, reason, status, created_at) VALUES ('c1', 'x', 'u', 'scam', 'open', '2026-11-15 00:00:00')"))
    _relax_stale_not_null(engine)
    with engine.begin() as conn:
        notnull = {row[1]: row[3] for row in conn.execute(text("PRAGMA table_info(moderation_case)"))}
        assert notnull["content_id"] == 0 and notnull["reporter_id"] == 0
        assert conn.execute(text("SELECT id, reason FROM moderation_case")).all() == [("c1", "scam")]
        conn.execute(text("INSERT INTO moderation_case (id, reported_user_id, reason, detail, status, created_at) VALUES ('c2', 'u2', 'scam', '', 'open', '2026-11-15 00:00:00')"))
    engine.dispose()


def test_reason_is_recorded_and_shown_in_detail(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")
    author_id = user_id(client, "author@example.com")
    with client.session_factory() as session:
        session.add(ModerationCase(content_id=content_id, reason="scam", detail="假房源"))
        session.commit()

    client.post(f"/api/v1/admin/contents/{content_id}/status", headers=headers(boss), json={"action": "remove", "reason": "虚假房源"})
    client.post(f"/api/v1/admin/users/{author_id}/status", headers=headers(boss), json={"status": "suspended", "reason": "多次发布虚假信息"})

    content = client.get(f"/api/v1/admin/contents/{content_id}", headers=headers(boss)).json()
    assert (content["title"], content["body"], content["status"], content["author_name"]) == ("后台测试帖", "正文", "deleted", "author")
    assert (content["history"][0]["action"], content["history"][0]["actor_name"], content["history"][0]["detail"]) == (
        "admin.content.remove",
        "boss",
        "虚假房源",
    )
    assert [case["detail"] for case in content["cases"]] == ["假房源"]

    user = client.get(f"/api/v1/admin/users/{author_id}", headers=headers(boss)).json()
    assert (user["email"], user["status"], user["post_count"]) == ("author@example.com", "suspended", 0)
    assert [post["content_id"] for post in user["posts"]] == [content_id]
    assert user["history"][0]["detail"] == "永久：多次发布虚假信息"
    audit = client.get("/api/v1/admin/audit?action=admin.user", headers=headers(boss)).json()["items"]
    assert audit[0]["detail"] == "永久：多次发布虚假信息"

    # 处理举报时填的理由也要进日志
    with client.session_factory() as session:
        case_id = session.scalar(select(ModerationCase.id))
    client.post(f"/api/v1/moderation/cases/{case_id}/decision", headers=headers(boss), json={"decision": "dismiss", "note": "已处理过"})
    with client.session_factory() as session:
        assert session.scalar(select(AuditLog.detail).where(AuditLog.action == "moderation.dismiss")) == "已处理过"


def test_grant_and_revoke_admin(client):
    boss = register(client, "boss@example.com", admin=True)
    helper = register(client, "helper@example.com")
    helper_id = user_id(client, "helper@example.com")
    url = f"/api/v1/admin/users/{helper_id}/admin"

    assert client.get("/api/v1/admin/stats", headers=headers(helper)).status_code == 403
    assert client.post(url, headers=headers(boss), json={"is_admin": True}).status_code == 200
    assert client.get("/api/v1/admin/stats", headers=headers(helper)).status_code == 401  # 前台令牌不能操作后台
    helper = admin_login(client, "helper@example.com")
    assert client.get("/api/v1/admin/stats", headers=headers(helper)).status_code == 200
    assert client.post(url, headers=headers(boss), json={"is_admin": True}).status_code == 409
    assert client.post(url, headers=headers(boss), json={"is_admin": False}).status_code == 200
    assert client.get("/api/v1/admin/stats", headers=headers(helper)).status_code == 403  # 撤销后立刻失效
    boss_id = user_id(client, "boss@example.com")
    assert client.post(f"/api/v1/admin/users/{boss_id}/admin", headers=headers(boss), json={"is_admin": False}).status_code == 409  # 不能撤自己
    assert audit_actions(client) == ["admin.user.grant", "admin.user.revoke"]


def test_certify_feature_and_announce(client):
    boss = register(client, "boss@example.com", admin=True)
    channel_id, content_id = seed(client, "boss@example.com")
    with client.session_factory() as session:
        room = Channel(code="room-x", name_hans="用户房间", name_hant="用戶房間", kind="room", is_active=True, owner_id=user_id(client, "boss@example.com"))
        session.add(room)
        session.commit()
        room_id = room.id

    # 认证：官方频道天然认证，不能改；用户房间可以加 / 取消
    assert client.post(f"/api/v1/admin/channels/{channel_id}/certified", headers=headers(boss), json={"certified": True}).status_code == 409
    assert client.post(f"/api/v1/admin/channels/{room_id}/certified", headers=headers(boss), json={"certified": True}).status_code == 200
    listed = client.get("/api/v1/admin/channels?q=room-x", headers=headers(boss)).json()["items"][0]
    assert (listed["is_certified"], listed["certified"]) == (True, True)
    with client.session_factory() as session:
        assert session.get(Channel, room_id).certified is True and session.get(Channel, channel_id).certified is True

    # 精选
    url = f"/api/v1/admin/contents/{content_id}/featured"
    assert client.post(url, headers=headers(boss), json={"featured": True}).status_code == 200
    assert client.post(url, headers=headers(boss), json={"featured": True}).status_code == 409
    assert client.get("/api/v1/admin/contents?q=后台", headers=headers(boss)).json()["items"][0]["featured"] is True
    assert client.post(url, headers=headers(boss), json={"featured": False}).status_code == 200

    # 公告
    options = client.get("/api/v1/admin/channel-options", headers=headers(boss)).json()["items"]
    assert {"channel_id": channel_id, "name": "后台测试"} in options
    made = client.post("/api/v1/admin/announcements", headers=headers(boss), json={"title": "维护通知", "body": "今晚十点维护。", "channel_id": channel_id})
    assert made.status_code == 200, made.text
    public = client.get(f"/api/v1/contents/{made.json()['content_id']}").json()
    assert (public["title"], public["status"]) == ("维护通知", "published")
    missing = client.post("/api/v1/admin/announcements", headers=headers(boss), json={"title": "x", "body": "内容内容", "channel_id": "missing"})
    assert missing.status_code == 404
    assert audit_actions(client) == [
        "admin.channel.certify",
        "admin.content.feature",
        "admin.content.unfeature",
        "admin.announcement.create",
    ]


def test_featured_content_ranks_first_for_guests(client):
    boss = register(client, "boss@example.com", admin=True)
    boss_id = user_id(client, "boss@example.com")  # 测试库共用一个连接：别在下面的会话里再开会话
    with client.session_factory() as session:
        channel = Channel(code="uk-feat", name_hans="精选测试", name_hant="精選測試", kind="official_auto", is_active=True, region_code="GLOBAL")
        session.add(channel)
        session.flush()
        ids = []
        for index in range(3):
            content = Content(type="post", status="published", title=f"普通 {index}", author_id=boss_id)
            session.add(content)
            session.flush()
            session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
            ids.append(content.id)
        session.commit()
    picked = ids[0]
    client.post(f"/api/v1/admin/contents/{picked}/featured", headers=headers(boss), json={"featured": True})
    feed = client.get("/api/v1/me/feed?tab=foryou").json()["items"]
    assert feed[0]["content_id"] == picked
    assert (feed[0]["featured"], feed[0]["reason"]) == (True, "编辑精选")


COUNTRY = ["资讯", "交流", "招聘", "房产", "市场", "商务"]


def public_names(client, region: str) -> list[str]:
    items = client.get(f"/api/v1/channels?region_code={region}").json()["items"]
    return [item["name_hans"] for item in items]


def open_codes(client, token: str) -> list[str]:
    body = client.get("/api/v1/me/regions", headers=headers(token)).json()
    return [item["code"] for item in body["open_regions"]]


def test_open_country_creates_its_channels_in_order(client):
    boss = register(client, "boss@example.com", admin=True)
    with client.session_factory() as session:
        session.add(RegionOpenRequest(user_id=user_id(client, "boss@example.com"), region_code="US"))
        session.commit()
    before = client.get("/api/v1/admin/regions", headers=headers(boss)).json()
    assert [item["code"] for item in before["items"]] == ["UK", "GLOBAL"]
    assert before["requests"] == [{"code": "US", "count": 1}]

    opened = client.post("/api/v1/admin/regions", headers=headers(boss), json={"code": "us", "name": "美国", "city": "纽约"})
    assert opened.status_code == 200, opened.text
    assert opened.json()["channels"] == ["美国" + name for name in COUNTRY]
    assert public_names(client, "US") == ["美国" + name for name in COUNTRY]  # 前台按这个顺序排
    assert open_codes(client, boss) == ["UK", "US", "GLOBAL"]
    after = client.get("/api/v1/admin/regions", headers=headers(boss)).json()
    assert after["requests"] == []
    assert {"code": "US", "name": "美国", "city": "纽约", "is_open": True, "channel_count": 6} in after["items"]

    # 用户可以把浏览国家切到新开通的国家
    switched = client.post("/api/v1/me/regions", headers=headers(boss), json={"region_code": "US", "source": "manual", "browse_region_code": "US"})
    assert switched.status_code == 200, switched.text

    assert client.post("/api/v1/admin/regions", headers=headers(boss), json={"code": "US", "name": "美国"}).status_code == 409
    assert client.post("/api/v1/admin/regions/US/channels", headers=headers(boss)).json()["channels"] == []  # 不重复建

    # 关闭后前台不再列出；重新开通不会多出频道
    assert client.post("/api/v1/admin/regions/US/open", headers=headers(boss), json={"open": False, "reason": "暂停运营"}).status_code == 200
    assert open_codes(client, boss) == ["UK", "GLOBAL"]
    assert public_names(client, "US") == []  # 关闭后它的频道不再列出，也搜不到
    assert [item for item in client.get("/api/v1/channels").json()["items"] if item["region_code"] == "US"] == []
    assert client.get("/api/v1/search?q=美国资讯").json()["channels"] == []
    assert client.post("/api/v1/admin/regions/US/open", headers=headers(boss), json={"open": False}).status_code == 409
    assert client.post("/api/v1/admin/regions/US/open", headers=headers(boss), json={"open": True}).status_code == 200
    assert len(public_names(client, "US")) == 6
    assert audit_actions(client) == ["admin.region.open", "region.set", "admin.region.close", "admin.region.open"]


def test_builtin_regions_fill_and_close(client):
    boss = register(client, "boss@example.com", admin=True)
    with client.session_factory() as session:
        session.add(Channel(code="uk-housing", name_hans="英国租房", name_hant="英國租房", kind="official_curated", region_code="UK", category="房产", is_active=True))
        session.commit()

    # 英国已有房产频道：保留原名，只补其余五个
    filled = client.post("/api/v1/admin/regions/UK/channels", headers=headers(boss)).json()["channels"]
    assert filled == ["英国资讯", "英国交流", "英国招聘", "英国市场", "英国商务"]
    assert public_names(client, "UK") == ["英国资讯", "英国交流", "英国招聘", "英国租房", "英国市场", "英国商务"]

    # 国际频道各国共享：不加国家名，不能关闭
    shared = client.post("/api/v1/admin/regions/GLOBAL/channels", headers=headers(boss)).json()["channels"]
    assert shared == ["新闻", "影视", "健康", "科技", "交友", "旅游"]
    assert client.post("/api/v1/admin/regions/GLOBAL/open", headers=headers(boss), json={"open": False}).status_code == 409

    # 内置的英国也可以关闭和重开
    assert client.post("/api/v1/admin/regions/UK/open", headers=headers(boss), json={"open": False}).status_code == 200
    assert open_codes(client, boss) == ["GLOBAL"]
    assert client.post("/api/v1/admin/regions/UK/open", headers=headers(boss), json={"open": True}).status_code == 200
    assert open_codes(client, boss) == ["UK", "GLOBAL"]
    assert client.post("/api/v1/admin/regions/JP/channels", headers=headers(boss)).status_code == 404  # 没开通的国家不能补频道


def test_create_and_edit_channel(client):
    boss = register(client, "boss@example.com", admin=True)
    url = "/api/v1/admin/channels"
    body = {"code": "uk-food", "name_hans": "英国美食", "region_code": "uk", "category": "美食", "sort_order": 7}

    assert client.post(url, headers=headers(boss), json={**body, "region_code": "JP"}).status_code == 422  # 国家没开通
    assert client.post(url, headers=headers(boss), json={**body, "code": "UK Food"}).status_code == 422  # 代号格式不对
    made = client.post(url, headers=headers(boss), json=body)
    assert made.status_code == 200, made.text
    channel_id = made.json()["channel_id"]
    assert client.post(url, headers=headers(boss), json=body).status_code == 409  # 代号重复

    row = client.get("/api/v1/admin/channels?region=UK", headers=headers(boss)).json()["items"][0]
    assert (row["code"], row["name"], row["name_hant"], row["region_code"], row["category"], row["sort_order"], row["is_active"]) == (
        "uk-food",
        "英国美食",
        "英国美食",
        "UK",
        "美食",
        7,
        True,
    )
    assert public_names(client, "UK") == ["英国美食"]

    edited = client.patch(
        f"{url}/{channel_id}",
        headers=headers(boss),
        json={"name_hans": "英国餐饮", "name_hant": "英國餐飲", "region_code": "GLOBAL", "category": "", "sort_order": 2},
    )
    assert edited.status_code == 200, edited.text
    row = client.get("/api/v1/admin/channels?q=uk-food", headers=headers(boss)).json()["items"][0]
    assert (row["name"], row["name_hant"], row["region_code"], row["category"], row["sort_order"]) == ("英国餐饮", "英國餐飲", "GLOBAL", "", 2)
    assert client.patch(f"{url}/missing", headers=headers(boss), json={"name_hans": "x", "region_code": "UK"}).status_code == 404
    assert audit_actions(client) == ["admin.channel.create", "admin.channel.update"]


def test_delete_channel_only_when_empty(client):
    boss = register(client, "boss@example.com", admin=True)
    boss_id = user_id(client, "boss@example.com")
    with client.session_factory() as session:
        empty = Channel(code="uk-empty", name_hans="建错的频道", name_hant="建錯的頻道", kind="official_curated", region_code="UK", is_active=True)
        busy = Channel(code="uk-busy", name_hans="有帖子的频道", name_hant="有帖子的頻道", kind="official_curated", region_code="UK", is_active=True)
        post = Content(type="post", status="published", title="一条帖子", author_id=boss_id)
        session.add_all([empty, busy, post])
        session.flush()
        session.add(ChannelItem(channel_id=busy.id, content_id=post.id))
        session.add(ChannelSubscription(user_id=boss_id, channel_id=empty.id))
        session.commit()
        empty_id, busy_id = empty.id, busy.id

    refused = client.post(f"/api/v1/admin/channels/{busy_id}/delete", headers=headers(boss), json={})
    assert refused.status_code == 409 and refused.json()["code"] == "CHANNEL_NOT_EMPTY"
    assert "1 条内容" in refused.json()["message"]
    with client.session_factory() as session:
        assert session.get(Channel, busy_id) is not None  # 没带 with_content：什么都没动

    removed = client.post(f"/api/v1/admin/channels/{empty_id}/delete", headers=headers(boss), json={"reason": "建错了"})
    assert removed.status_code == 200, removed.text
    assert public_names(client, "UK") == ["有帖子的频道"]
    with client.session_factory() as session:
        assert session.get(Channel, empty_id) is None
        assert session.scalar(select(ChannelSubscription.user_id).where(ChannelSubscription.channel_id == empty_id)) is None
        assert session.scalar(select(AuditLog.detail).where(AuditLog.action == "admin.channel.delete")) == "建错的频道（uk-empty）：建错了"
    assert client.post(f"/api/v1/admin/channels/{empty_id}/delete", headers=headers(boss), json={}).status_code == 404
    assert audit_actions(client) == ["admin.channel.delete"]  # 被拒绝的那次不记日志


def test_delete_channel_with_its_content(client, tmp_path, monkeypatch):
    from app.api.v1 import uploads

    monkeypatch.setattr(uploads, "upload_root", lambda: tmp_path)
    boss = register(client, "boss@example.com", admin=True)
    boss_id = user_id(client, "boss@example.com")
    comment_image, post_image = "c" * 32, "d" * 32  # 一张只在留言里，一张留言和别的帖子都在用
    for name in (comment_image, post_image):
        (tmp_path / name).write_bytes(b"img")
    with client.session_factory() as session:
        doomed = Channel(code="uk-doomed", name_hans="要删的频道", name_hant="要刪的頻道", kind="official_curated", region_code="UK", is_active=True)
        other = Channel(code="uk-other", name_hans="别的频道", name_hant="別的頻道", kind="official_curated", region_code="UK", is_active=True)
        session.add_all([doomed, other])
        session.flush()
        room = Channel(code="room-kid", name_hans="下属房间", name_hant="下屬房間", kind="room", region_code="UK", is_active=True, owner_id=boss_id, parent_channel_id=doomed.id)
        only_here = Content(type="post", status="published", title="只在这个频道", author_id=boss_id)
        shared = Content(type="post", status="published", title="两个频道都有", author_id=boss_id, image_key=post_image)
        session.add_all([room, only_here, shared])
        session.flush()
        session.add_all(
            [
                ChannelItem(channel_id=doomed.id, content_id=only_here.id),
                ChannelItem(channel_id=doomed.id, content_id=shared.id),
                ChannelItem(channel_id=other.id, content_id=shared.id),
                RoomComment(room_id=doomed.id, content_id=only_here.id, author_id=boss_id, body="一条留言", status="published", image_key=comment_image),
                RoomComment(room_id=doomed.id, author_id=boss_id, body="", status="published", image_key=post_image),
                UploadObject(key=comment_image, owner_id=boss_id, content_type="image/png", stored=True),
                ModerationCase(reported_channel_id=doomed.id, reason="scam"),
            ]
        )
        session.commit()
        doomed_id, room_id, only_id, shared_id = doomed.id, room.id, only_here.id, shared.id
    url = f"/api/v1/admin/channels/{doomed_id}/delete"

    # 两道保护：要显式 with_content，还要输对频道名
    assert client.post(url, headers=headers(boss), json={}).status_code == 409
    wrong = client.post(url, headers=headers(boss), json={"with_content": True, "confirm_name": "别的频道"})
    assert wrong.status_code == 422
    with client.session_factory() as session:
        assert session.get(Channel, doomed_id) is not None and session.get(Content, only_id).status == "published"

    done = client.post(url, headers=headers(boss), json={"with_content": True, "confirm_name": "要删的频道", "reason": "合并频道"})
    assert done.status_code == 200, done.text
    assert done.json() == {"deleted": True, "removed_posts": 1, "removed_comments": 2, "detached_rooms": 1, "files_left": 0}
    assert not (tmp_path / comment_image).exists()  # 留言里的图片连文件一起删，原链接打不开了
    assert (tmp_path / post_image).exists()  # 还有帖子在用的图片保留
    assert client.get(f"/api/v1/uploads/{comment_image}").status_code == 404

    with client.session_factory() as session:
        assert session.get(Channel, doomed_id) is None
        assert session.get(Content, only_id).status == "deleted"  # 只属于这个频道的帖子一并下架
        assert session.get(Content, shared_id).status == "published"  # 别的频道里还有的帖子不动
        assert session.scalar(select(ChannelItem.channel_id).where(ChannelItem.content_id == shared_id)) is not None
        assert session.scalar(select(RoomComment.id).where(RoomComment.room_id == doomed_id)) is None
        kept = session.get(Channel, room_id)
        assert kept is not None and kept.parent_channel_id is None and kept.is_active  # 下属房间保留，只解除归属
        assert session.scalar(select(ModerationCase.status).where(ModerationCase.reported_channel_id == doomed_id)) == "closed"
        detail = session.scalar(select(AuditLog.detail).where(AuditLog.action == "admin.channel.delete"))
    assert detail == "要删的频道（uk-doomed），连同 1 条内容、2 条留言，解除 1 个房间的归属：合并频道"
    assert client.get(f"/api/v1/contents/{only_id}").status_code == 404
    assert client.get(f"/api/v1/contents/{shared_id}").status_code == 200
    assert client.get("/api/v1/admin/queue", headers=headers(boss)).json()["cases"] == []


def test_delete_content_permanently(client, tmp_path, monkeypatch):
    from app.api.v1 import uploads

    monkeypatch.setattr(uploads, "upload_root", lambda: tmp_path)
    boss = register(client, "boss@example.com", admin=True)
    boss_id = user_id(client, "boss@example.com")
    for name in ("a" * 32, "b" * 32):
        (tmp_path / name).write_bytes(b"img")
    with client.session_factory() as session:
        channel = Channel(code="uk-del", name_hans="删帖测试", name_hant="刪帖測試", kind="official_curated", region_code="UK", is_active=True)
        doomed = Content(type="post", status="published", title="要删的帖子", author_id=boss_id, image_key="a" * 32, image_keys_json='["' + "a" * 32 + '", "' + "b" * 32 + '"]')
        other = Content(type="post", status="published", title="别的帖子", author_id=boss_id, image_key="b" * 32)  # 和要删的帖子共用一张图
        session.add_all([channel, doomed, other, UploadObject(key="a" * 32, owner_id=boss_id, content_type="image/png", stored=True)])
        session.flush()
        session.add_all(
            [
                ChannelItem(channel_id=channel.id, content_id=doomed.id),
                ChannelItem(channel_id=channel.id, content_id=other.id),
                RoomComment(room_id=channel.id, content_id=doomed.id, author_id=boss_id, body="留言", status="published"),
                ContentReaction(user_id=boss_id, content_id=doomed.id, liked=True),
                ModerationCase(content_id=doomed.id, reason="scam"),
                Notification(user_id=boss_id, kind="mention", body="有人提到你", content_id=doomed.id),
            ]
        )
        session.commit()
        doomed_id, other_id = doomed.id, other.id

    removed = client.post(f"/api/v1/admin/contents/{doomed_id}/delete", headers=headers(boss), json={"reason": "广告"})
    assert removed.status_code == 200, removed.text
    with client.session_factory() as session:
        assert session.get(Content, doomed_id) is None
        assert session.get(Content, other_id) is not None
        for model in (ChannelItem, RoomComment, ContentReaction, ModerationCase, Notification):
            assert session.scalar(select(func.count()).select_from(model).where(model.content_id == doomed_id)) == 0, model.__name__
        assert session.get(UploadObject, "a" * 32) is None
        assert session.scalar(select(AuditLog.detail).where(AuditLog.action == "admin.content.delete")) == "要删的帖子（post）：广告"
    assert not (tmp_path / ("a" * 32)).exists()  # 只有这条帖子在用的图片连文件一起删
    assert (tmp_path / ("b" * 32)).exists()  # 别的帖子还在用的图片保留
    assert client.get(f"/api/v1/contents/{doomed_id}").status_code == 404
    assert client.get("/api/v1/admin/queue", headers=headers(boss)).json()["cases"] == []
    assert client.post(f"/api/v1/admin/contents/{doomed_id}/delete", headers=headers(boss), json={}).status_code == 404


def test_moderation_needs_admin_and_cannot_suspend_admins(client):
    from app.api.v1.moderation import require_moderator

    client.app.dependency_overrides.pop(require_moderator)  # 去掉 conftest 里测试用的放行，测真实权限
    boss = register(client, "boss@example.com", admin=True)
    plain = register(client, "plain@example.com")
    boss_id = user_id(client, "boss@example.com")
    with client.session_factory() as session:
        case = ModerationCase(reported_user_id=boss_id, reason="scam")
        session.add(case)
        session.commit()
        case_id = case.id

    for url in (
        "/api/v1/moderation/x/decision",
        "/api/v1/moderation/comments/x/decision",
        "/api/v1/moderation/channels/x/decision",
        f"/api/v1/moderation/cases/{case_id}/decision",
    ):
        assert client.post(url, headers=headers(plain), json={"decision": "approve"}).status_code == 403, url

    # 管理员被举报：处理举报时不能把管理员（包括自己）封掉
    refused = client.post(f"/api/v1/moderation/cases/{case_id}/decision", headers=headers(boss), json={"decision": "remove"})
    assert refused.status_code == 409 and refused.json()["code"] == "CANNOT_SUSPEND_ADMIN"
    assert client.get("/api/v1/me", headers=headers(boss)).status_code == 200
    with client.session_factory() as session:
        assert session.get(ModerationCase, case_id).status == "open"  # 被拒绝的处理不结案
    assert client.post(f"/api/v1/moderation/cases/{case_id}/decision", headers=headers(boss), json={"decision": "dismiss"}).status_code == 200


def test_restoring_a_pending_post_keeps_it_pending(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com", status="pending")
    url = f"/api/v1/admin/contents/{content_id}/status"
    assert client.post(url, headers=headers(boss), json={"action": "remove"}).status_code == 200
    assert client.post(url, headers=headers(boss), json={"action": "restore"}).json()["status"] == "pending"
    assert client.get(f"/api/v1/contents/{content_id}").status_code == 404  # 没审过的内容不会因为下架再恢复而公开


def test_user_page_lists_at_most_fifty_posts(client):
    register(client, "author@example.com")
    author_id = user_id(client, "author@example.com")
    with client.session_factory() as session:
        for index in range(55):
            session.add(Content(type="post", status="published", title=f"帖子 {index}", author_id=author_id))
        session.commit()
    assert len(client.get(f"/api/v1/users/{author_id}/posts").json()["items"]) == 50


def test_admin_reset_link_lets_user_set_a_new_password(client):
    boss = register(client, "boss@example.com", admin=True)
    old_token = register(client, "forgot@example.com")
    target_id = user_id(client, "forgot@example.com")
    login = lambda password: client.post("/api/v1/auth/login", json={"email": "forgot@example.com", "password": password})
    refresh = login("password-1").json()["refresh_token"]

    first = client.post(f"/api/v1/admin/users/{target_id}/reset-link", headers=headers(boss)).json()
    second = client.post(f"/api/v1/admin/users/{target_id}/reset-link", headers=headers(boss)).json()
    assert first["token"] != second["token"] and second["hours"] == 24
    reset = lambda token, password: client.post("/api/v1/auth/reset-password", json={"token": token, "password": password})

    assert reset(first["token"], "brand-new-pass").status_code == 400  # 新链接生成后旧链接作废
    assert reset("not-a-token", "brand-new-pass").status_code == 400
    assert reset(second["token"], "short").status_code == 422  # 新密码至少 8 位
    assert reset(second["token"], "brand-new-pass").status_code == 200
    assert reset(second["token"], "another-pass-1").status_code == 400  # 只能用一次

    assert login("password-1").status_code == 401
    assert login("brand-new-pass").status_code == 200
    # 其他设备上的登录全部失效：旧的续期令牌不能再用
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert old_token  # 旧 access token 最多再活 15 分钟（JWT 无法撤销），到期后续不上
    with client.session_factory() as session:
        stored = session.scalars(select(AuditLog.action).where(AuditLog.target_id == target_id).order_by(AuditLog.created_at)).all()
    assert "admin.user.reset_link" in stored and "account.password_reset" in stored


def test_delete_country_with_all_its_data(client):
    boss = register(client, "boss@example.com", admin=True)
    fan = register(client, "fan@example.com")
    assert client.post("/api/v1/admin/regions", headers=headers(boss), json={"code": "US", "name": "美国"}).status_code == 200
    assert client.post("/api/v1/me/regions", headers=headers(fan), json={"region_code": "US", "source": "manual"}).status_code == 200
    with client.session_factory() as session:
        us_channel = session.scalar(select(Channel).where(Channel.region_code == "US"))
        room = Channel(code="us-room", name_hans="美国房间", name_hant="美國房間", kind="room", region_code="US", parent_channel_id=us_channel.id, is_active=True)
        post = Content(type="post", status="published", title="美国帖", body="正文", published_at=utcnow())
        session.add_all([room, post])
        session.flush()
        session.add(ChannelItem(channel_id=us_channel.id, content_id=post.id))
        session.commit()
        post_id = post.id

    # 国际各国共享不能删；国家名要原样输入
    assert client.post("/api/v1/admin/regions/GLOBAL/delete", headers=headers(boss), json={"confirm_name": "国际"}).status_code == 409
    assert client.post("/api/v1/admin/regions/US/delete", headers=headers(boss), json={"confirm_name": "美"}).status_code == 422
    assert client.post("/api/v1/admin/regions/US/delete", headers=headers(fan), json={"confirm_name": "美国"}).status_code in (401, 403)

    done = client.post("/api/v1/admin/regions/US/delete", headers=headers(boss), json={"confirm_name": "美国", "reason": "不做了"})
    assert done.status_code == 200, done.text
    assert done.json()["removed_posts"] == 1
    with client.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Channel).where(Channel.region_code == "US")) == 0
        assert session.get(Content, post_id).deleted_at is not None
        assert session.get(UserRegionPref, user_id(client, "fan@example.com")).region_code == "GLOBAL"
    codes = [item["code"] for item in client.get("/api/v1/admin/regions", headers=headers(boss)).json()["items"]]
    assert "US" not in codes
    assert "US" not in open_codes(client, fan)  # 选了美国的用户回到国际
    assert "admin.region.delete" in audit_actions(client)

    # 英国是内置国家：删除后保持关闭，不会自动重新出现
    assert client.post("/api/v1/admin/regions/UK/delete", headers=headers(boss), json={"confirm_name": "英国"}).status_code == 200
    assert "UK" not in open_codes(client, fan)


def test_dev_seed_still_runs_after_uk_is_deleted(client):
    """本地每次启动都会跑种子：英国删掉后不能重复插种子（会撞上还在的国际频道），也不能把英国频道补回来。"""
    from app.seed import ensure_seed

    boss = register(client, "boss@example.com", admin=True)
    with client.session_factory() as session:
        ensure_seed(session)  # 空库：插入种子（含 uk-housing 和 global-chinese）
        session.commit()
    assert client.post("/api/v1/admin/regions/UK/delete", headers=headers(boss), json={"confirm_name": "英国"}).status_code == 200
    with client.session_factory() as session:
        ensure_seed(session)  # 相当于重启后端
        session.commit()
        assert session.scalar(select(func.count()).select_from(Channel).where(Channel.region_code == "UK")) == 0
        assert session.scalar(select(func.count()).select_from(Channel).where(Channel.code == "global-chinese")) == 1

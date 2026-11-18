"""后台加固与运营工具：权限分级、两步验证、审计来源、限时封禁、通知、批量、认领、自动拦截、导出、用户数据请求。"""
import time
from datetime import timedelta

from sqlalchemy import select, update

from app.core.security import totp_code
from app.guard import AUTO_HIDE_REPORTS, blocked_term_in
from app.models import AuditLog, BlockedTerm, Content, Notification, ReviewClaim, User, utcnow
from tests.test_admin import admin_login, headers, register, seed, user_id


def moderator(client, email: str) -> str:
    """普通管理员（不是超级管理员）的后台令牌。"""
    register(client, email)
    with client.session_factory() as session:
        session.scalar(select(User).where(User.email == email)).is_admin = True
        session.commit()
    return admin_login(client, email)


def pending_posts(client, author_email: str, count: int) -> list[str]:
    with client.session_factory() as session:
        rows = [Content(type="post", status="pending", title=f"待审 {index}", author_id=user_id(client, author_email)) for index in range(count)]
        session.add_all(rows)
        session.commit()
        return [row.id for row in rows]


def test_moderator_can_moderate_but_not_do_super_only_things(client):
    register(client, "boss@example.com", admin=True)
    mod = moderator(client, "mod@example.com")
    register(client, "author@example.com")
    channel_id, content_id = seed(client, "author@example.com")
    author_id = user_id(client, "author@example.com")

    assert client.get("/api/v1/admin/me", headers=headers(mod)).json()["is_super"] is False
    assert client.get("/api/v1/admin/stats", headers=headers(mod)).status_code == 200
    assert client.post(f"/api/v1/admin/contents/{content_id}/status", headers=headers(mod), json={"action": "remove"}).status_code == 200
    assert client.post(f"/api/v1/admin/channels/{channel_id}/active", headers=headers(mod), json={"active": False}).status_code == 200

    denied = [
        ("post", f"/api/v1/admin/contents/{content_id}/delete", {}),
        ("post", "/api/v1/admin/channels", {"code": "new-one", "name_hans": "新频道", "region_code": "UK"}),
        ("post", f"/api/v1/admin/channels/{channel_id}/delete", {}),
        ("post", "/api/v1/admin/regions", {"code": "US", "name": "美国"}),
        ("post", f"/api/v1/admin/users/{author_id}/admin", {"is_admin": True}),
        ("post", f"/api/v1/admin/users/{author_id}/reset-link", None),
        ("post", f"/api/v1/admin/users/{author_id}/erase", {"confirm_email": "author@example.com"}),
        ("get", f"/api/v1/admin/users/{author_id}/export", None),
        ("get", "/api/v1/admin/export/users", None),
        ("post", "/api/v1/admin/terms", {"term": "博彩"}),
    ]
    for method, url, body in denied:
        response = client.request(method, url, headers=headers(mod), json=body)
        assert (response.status_code, response.json()["code"]) == (403, "SUPER_ONLY"), url


def test_grant_levels_and_revoke_kills_admin_sessions(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "helper@example.com")
    helper_id = user_id(client, "helper@example.com")
    url = f"/api/v1/admin/users/{helper_id}/admin"

    assert client.post(url, headers=headers(boss), json={"is_admin": True}).json()["is_super"] is False
    assert client.post(url, headers=headers(boss), json={"is_admin": True, "is_super": True}).json()["is_super"] is True
    login = client.post("/api/v1/admin/login", json={"email": "helper@example.com", "password": "password-1"}).json()
    assert client.post(url, headers=headers(boss), json={"is_admin": False}).json() == {"user_id": helper_id, "is_admin": False, "is_super": False}
    # 撤销后：手里的访问令牌立刻没用，续期令牌也续不出来
    assert client.get("/api/v1/admin/stats", headers=headers(login["access_token"])).status_code == 403
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401


def test_admin_session_survives_refresh_and_front_tokens_are_refused(client):
    register(client, "boss@example.com", admin=True)
    login = client.post("/api/v1/admin/login", json={"email": "boss@example.com", "password": "password-1"}).json()
    renewed = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}).json()
    assert client.get("/api/v1/admin/stats", headers=headers(renewed["access_token"])).status_code == 200

    front = client.post("/api/v1/auth/login", json={"email": "boss@example.com", "password": "password-1"}).json()
    refused = client.get("/api/v1/admin/stats", headers=headers(front["access_token"]))
    assert (refused.status_code, refused.json()["code"]) == (401, "ADMIN_LOGIN_REQUIRED")
    assert client.get("/api/v1/me", headers=headers(front["access_token"])).status_code == 200  # 前台照常能用


def test_two_factor_setup_login_and_disable(client):
    boss = register(client, "boss@example.com", admin=True)
    setup = client.post("/api/v1/admin/totp/setup", headers=headers(boss)).json()
    secret = setup["secret"]
    assert setup["qr_svg"].startswith("<svg")  # 手机扫码添加
    now = int(time.time()) // 30
    wrong = "000000" if totp_code(secret, now) != "000000" else "111111"
    assert client.post("/api/v1/admin/totp/enable", headers=headers(boss), json={"secret": secret, "code": wrong}).status_code == 400
    assert client.post("/api/v1/admin/totp/enable", headers=headers(boss), json={"secret": secret, "code": totp_code(secret, now)}).status_code == 200
    assert client.get("/api/v1/admin/me", headers=headers(boss)).json()["two_factor"] is True

    credentials = {"email": "boss@example.com", "password": "password-1"}
    assert client.post("/api/v1/admin/login", json=credentials).json()["code"] == "TOTP_REQUIRED"
    assert client.post("/api/v1/admin/login", json={**credentials, "code": wrong}).json()["code"] == "TOTP_INVALID"
    # 上一个时间片的验证码也接受（容忍时钟差）
    assert client.post("/api/v1/admin/login", json={**credentials, "code": totp_code(secret, now - 1)}).status_code == 200

    assert client.post("/api/v1/admin/totp/disable", headers=headers(boss), json={"code": wrong}).status_code == 400
    assert client.post("/api/v1/admin/totp/disable", headers=headers(boss), json={"code": totp_code(secret, now)}).status_code == 200
    assert client.post("/api/v1/admin/login", json=credentials).status_code == 200


def test_audit_records_where_the_action_came_from(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")
    client.post(
        f"/api/v1/admin/contents/{content_id}/status",
        headers={**headers(boss), "User-Agent": "TestBrowser/1.0", "X-Forwarded-For": "6.6.6.6"},
        json={"action": "remove"},
    )
    row = client.get("/api/v1/admin/audit?action=admin.content", headers=headers(boss)).json()["items"][0]
    # 没有声明在代理后面：伪造的 X-Forwarded-For 不算数，记的是真实连接的对端
    assert (row["ip"], row["user_agent"]) == ("testclient", "TestBrowser/1.0")


def test_timed_suspension_tells_the_user_why_and_lifts_itself(client):
    boss = register(client, "boss@example.com", admin=True)
    author = register(client, "author@example.com")
    author_id = user_id(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")
    refresh = client.post("/api/v1/auth/login", json={"email": "author@example.com", "password": "password-1"}).json()["refresh_token"]

    body = {"status": "suspended", "days": 7, "reason": "刷广告", "remove_contents": True}
    result = client.post(f"/api/v1/admin/users/{author_id}/status", headers=headers(boss), json=body).json()
    assert (result["removed_posts"], result["removed_comments"]) == (1, 0) and result["suspended_until"]
    assert client.get(f"/api/v1/contents/{content_id}").status_code == 404
    assert client.get("/api/v1/me", headers=headers(author)).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401  # 各设备上的登录都失效

    credentials = {"email": "author@example.com", "password": "password-1"}
    denied = client.post("/api/v1/auth/login", json=credentials)
    assert denied.status_code == 403 and "刷广告" in denied.json()["message"] and "到 " in denied.json()["message"]
    # 一并下架的帖子每条都有记录，之后可以恢复
    assert client.post(f"/api/v1/admin/contents/{content_id}/status", headers=headers(boss), json={"action": "restore"}).status_code == 200

    with client.session_factory() as session:
        session.get(User, author_id).suspended_until = utcnow() - timedelta(minutes=1)
        session.commit()
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 200  # 到期自动解封
    with client.session_factory() as session:
        user = session.get(User, author_id)
        assert (user.status, user.suspended_until, user.suspend_reason) == ("active", None, None)


def test_authors_are_told_what_happened_to_their_content(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    author_id = user_id(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")
    (pending_id,) = pending_posts(client, "author@example.com", 1)

    client.post(f"/api/v1/admin/contents/{content_id}/status", headers=headers(boss), json={"action": "remove", "reason": "含广告"})
    client.post(f"/api/v1/moderation/{pending_id}/decision", headers=headers(boss), json={"decision": "reject", "note": "重复发布"})
    with client.session_factory() as session:
        bodies = session.scalars(select(Notification.body).where(Notification.user_id == author_id).order_by(Notification.created_at)).all()
    assert bodies == ["你的「后台测试帖」已被管理员下架。原因：含广告", "你的「待审 0」没有通过审核。原因：重复发布"]


def test_batch_handles_each_item_and_reports_the_ones_it_could_not(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    ids = pending_posts(client, "author@example.com", 3)

    body = {"ids": [ids[0], ids[1], ids[0], "no-such-id"], "action": "approve"}
    result = client.post("/api/v1/admin/contents/batch", headers=headers(boss), json=body).json()
    assert result["done"] == 2 and [item["content_id"] for item in result["failed"]] == ["no-such-id"]
    removed = client.post("/api/v1/admin/contents/batch", headers=headers(boss), json={"ids": ids, "action": "remove", "reason": "清理"}).json()
    assert removed == {"done": 3, "failed": []}
    with client.session_factory() as session:
        assert {session.get(Content, item).status for item in ids} == {"deleted"}
    assert client.post("/api/v1/admin/contents/batch", headers=headers(boss), json={"ids": [], "action": "remove"}).status_code == 422


def test_claim_keeps_two_admins_off_the_same_item(client):
    boss = register(client, "boss@example.com", admin=True)
    mod = moderator(client, "mod@example.com")
    register(client, "author@example.com")
    (content_id,) = pending_posts(client, "author@example.com", 1)
    body = {"target_type": "content", "target_id": content_id}

    assert client.post("/api/v1/admin/claims", headers=headers(boss), json=body).status_code == 200
    assert client.post("/api/v1/admin/claims", headers=headers(boss), json=body).status_code == 200  # 自己可以重复认领
    taken = client.post("/api/v1/admin/claims", headers=headers(mod), json=body)
    assert taken.status_code == 409 and "boss" in taken.json()["message"]
    assert client.get("/api/v1/admin/queue", headers=headers(mod)).json()["contents"][0]["claimed_by"] == "boss"
    assert client.get("/api/v1/admin/queue", headers=headers(boss)).json()["contents"][0]["claimed_by"] == ""

    with client.session_factory() as session:
        session.get(ReviewClaim, ("content", content_id)).claimed_at = utcnow() - timedelta(minutes=11)
        session.commit()
    assert client.post("/api/v1/admin/claims", headers=headers(mod), json=body).status_code == 200  # 过期了就能接手
    assert client.get("/api/v1/admin/queue", headers=headers(boss)).json()["contents"][0]["claimed_by"] == "mod"


def test_blocked_terms_and_auto_hide_after_several_reports(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")

    assert client.post("/api/v1/admin/terms", headers=headers(boss), json={"term": " Casino.Example "}).json() == {"term": "casino.example"}
    assert client.post("/api/v1/admin/terms", headers=headers(boss), json={"term": "casino.example"}).status_code == 409
    assert [item["term"] for item in client.get("/api/v1/admin/terms", headers=headers(boss)).json()["items"]] == ["casino.example"]
    with client.session_factory() as session:
        assert blocked_term_in(session, "正常标题", "加我 https://CASINO.example/x 领奖") == "casino.example"
        assert blocked_term_in(session, "正常标题", None, "正常正文") is None
    assert client.post("/api/v1/admin/terms/delete", headers=headers(boss), json={"term": "casino.example"}).status_code == 200
    with client.session_factory() as session:
        assert session.get(BlockedTerm, "casino.example") is None

    # 刚注册的小号举报再多也不会自动隐藏（不然三个小号就能让任何帖子下线）
    for index in range(AUTO_HIDE_REPORTS):
        fresh = register(client, f"fresh{index}@example.com")
        assert client.post(f"/api/v1/contents/{content_id}/report", headers=headers(fresh), json={"reason": "scam"}).status_code == 200
    # 注册满 7 天的账号举报：攒够数自动隐藏，等管理员看
    for index in range(AUTO_HIDE_REPORTS):
        reporter = register(client, f"reporter{index}@example.com")
        with client.session_factory() as session:
            session.execute(update(User).where(User.email == f"reporter{index}@example.com").values(created_at=utcnow() - timedelta(days=8)))
            session.commit()
        assert client.get(f"/api/v1/contents/{content_id}").status_code == 200  # 还没够数，照常显示
        assert client.post(f"/api/v1/contents/{content_id}/report", headers=headers(reporter), json={"reason": "scam"}).status_code == 200
    assert client.get(f"/api/v1/contents/{content_id}").status_code == 404
    with client.session_factory() as session:
        assert session.get(Content, content_id).status == "pending"
        assert session.scalar(select(AuditLog.detail).where(AuditLog.action == "auto.hide")).startswith(f"{AUTO_HIDE_REPORTS} 条")


def test_exports_and_user_data_requests(client):
    boss = register(client, "boss@example.com", admin=True)
    author = register(client, "author@example.com")
    author_id = user_id(client, "author@example.com")
    _, content_id = seed(client, "author@example.com")
    with client.session_factory() as session:
        session.get(User, author_id).display_name = "=HYPERLINK(1)"  # 用 Excel 打开时不能被当成公式
        session.commit()

    users = client.get("/api/v1/admin/export/users", headers=headers(boss))
    assert users.headers["content-type"].startswith("text/csv") and "attachment" in users.headers["content-disposition"]
    assert users.text.startswith("﻿用户 ID,名字") and "author@example.com" in users.text and ",'=HYPERLINK(1)," in users.text
    assert "后台测试帖" in client.get("/api/v1/admin/export/contents", headers=headers(boss)).text
    assert "admin.export" in client.get("/api/v1/admin/export/audit", headers=headers(boss)).text  # 导出本身也留了记录
    assert client.get("/api/v1/admin/export/passwords", headers=headers(boss)).status_code == 422

    data = client.get(f"/api/v1/admin/users/{author_id}/export", headers=headers(boss)).json()
    assert data["user"]["email"] == "author@example.com" and [post["content_id"] for post in data["posts"]] == [content_id]

    url = f"/api/v1/admin/users/{author_id}/erase"
    assert client.post(url, headers=headers(boss), json={"confirm_email": "someone@example.com"}).status_code == 422
    assert client.post(url, headers=headers(boss), json={"confirm_email": "Author@Example.com", "reason": "本人来信要求"}).status_code == 200
    with client.session_factory() as session:
        user = session.get(User, author_id)
        assert user.deleted_at is not None and "author" not in user.email and session.get(Content, content_id).status == "deleted"
        assert session.scalar(select(AuditLog.detail).where(AuditLog.action == "admin.user.erase")) == "本人来信要求"
    assert client.get("/api/v1/me", headers=headers(author)).status_code == 401
    boss_id = user_id(client, "boss@example.com")
    assert client.post(f"/api/v1/admin/users/{boss_id}/erase", headers=headers(boss), json={"confirm_email": "boss@example.com"}).status_code == 409


def test_overview_metrics_and_health(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    ids = pending_posts(client, "author@example.com", 2)
    with client.session_factory() as session:
        session.get(Content, ids[0]).created_at = utcnow() - timedelta(hours=30)  # 等了超过一天
        session.commit()

    stats = client.get("/api/v1/admin/stats", headers=headers(boss)).json()
    assert (stats["overdue_contents"], stats["overdue_cases"], stats["avg_review_hours"]) == (1, 0, None)
    client.post(f"/api/v1/moderation/{ids[0]}/decision", headers=headers(boss), json={"decision": "approve"})
    stats = client.get("/api/v1/admin/stats", headers=headers(boss)).json()
    assert stats["overdue_contents"] == 0 and 29.9 <= stats["avg_review_hours"] <= 30.1
    assert {"active_users_7d", "cases_closed_30d", "cases_upheld_30d", "posts_by_region", "server_errors_1h"} <= stats.keys()

    health = client.get("/api/v1/admin/health", headers=headers(boss)).json()
    assert (health["storage"], health["storage_ok"]) == ("本地磁盘", True) and health["oldest_pending"] and health["oldest_case"] is None


def test_content_detail_gives_the_reviewer_the_video(client):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "author@example.com")
    author_id = user_id(client, "author@example.com")
    with client.session_factory() as session:
        uploaded = Content(type="video", status="pending", title="上传的视频", author_id=author_id, video_key="a" * 32)
        linked = Content(type="post", status="pending", title="外链视频", author_id=author_id, embed_media_id="abc", embed_source_url="https://youtu.be/abc")
        plain = Content(type="post", status="pending", title="纯文字", author_id=author_id)
        session.add_all([uploaded, linked, plain])
        session.commit()
        ids = [uploaded.id, linked.id, plain.id]

    details = [client.get(f"/api/v1/admin/contents/{item}", headers=headers(boss)).json() for item in ids]
    assert [(row["has_video"], row["video_url"], row["embed_url"]) for row in details] == [
        (True, "/api/v1/uploads/" + "a" * 32, ""),
        (True, "", "https://youtu.be/abc"),
        (False, "", ""),
    ]


def test_review_switches_let_new_content_publish_directly(client):
    boss = register(client, "boss@example.com", admin=True)
    mod = moderator(client, "mod@example.com")
    author = register(client, "author@example.com")
    assert client.post("/api/v1/auth/verify-phone", headers=headers(author), json={"phone": "+447700902222", "code": "246810"}).status_code == 200
    channel_id, content_id = seed(client, "author@example.com")
    with client.session_factory() as session:
        from app.models import Channel, ChannelItem

        market = Channel(code="g-market-sw", name_hans="市场", name_hant="市场", kind="official_curated", category="市场", region_code="GLOBAL", is_active=True)
        session.add_all([market, ChannelItem(channel_id=channel_id, content_id=content_id)])
        session.commit()
        market_id = market.id

    def post() -> str:
        return client.post("/api/v1/contents", headers=headers(author), json={"channel_id": channel_id, "title": "新帖", "body": "正文"}).json()["status"]

    def comment(text: str = "不错") -> str:
        return client.post(f"/api/v1/contents/{content_id}/comments", headers=headers(author), json={"body": text}).json()["status"]

    def listing() -> str:
        body = {"channel_id": market_id, "title": "书桌", "body": "九成新书桌转让", "category": "市场", "kind": "secondhand",
                "area": "伦敦", "price_amount": "40", "price_unit": "", "contact": "sms: 1", "attrs": {}}
        return client.post("/api/v1/listings", headers=headers(author), json=body).json()["status"]

    # 默认都要审
    assert client.get("/api/v1/admin/review-settings", headers=headers(mod)).json() == {"post": True, "listing": True, "comment": True}
    assert (post(), comment(), listing()) == ("pending", "pending", "pending")

    # 只有超级管理员能改；改了记审计
    off = {"kind": "comment", "enabled": False}
    assert client.post("/api/v1/admin/review-settings", headers=headers(mod), json=off).status_code == 403
    assert client.post("/api/v1/admin/review-settings", headers=headers(boss), json=off).json()["comment"] is False
    assert client.post("/api/v1/admin/review-settings", headers=headers(boss), json=off).status_code == 409
    for kind in ("post", "listing"):
        assert client.post("/api/v1/admin/review-settings", headers=headers(boss), json={"kind": kind, "enabled": False}).status_code == 200
    assert (post(), comment(), listing()) == ("published", "published", "published")
    with client.session_factory() as session:
        assert session.scalar(select(AuditLog).where(AuditLog.action == "admin.review.off", AuditLog.detail == "comment")) is not None
        session.add(BlockedTerm(term="casino"))
        session.commit()

    # 关了审核，敏感词照样拦
    assert comment("来 Casino 玩") == "pending"

    # 再打开就恢复要审
    assert client.post("/api/v1/admin/review-settings", headers=headers(boss), json={"kind": "comment", "enabled": True}).json()["comment"] is True
    assert comment() == "pending"

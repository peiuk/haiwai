"""第三轮全库审计补的规则：每条对应一个能被利用或会出错的具体情况。"""
from app.api.v1 import contents, uploads
from app.core.config import get_settings
from app.models import ChannelItem, Content, ListingExt, RoomComment
from tests.test_admin import register as register_admin
from tests.test_h5_domain import approve, headers, housing_channel, register, verify
from tests.test_room_owner_manage import _live_room, _post


def _me(client, token: str) -> str:
    return client.get("/api/v1/me", headers=headers(token)).json()["user_id"]


def _published_post(client, author: str, channel_id: str, **extra) -> str:
    created = client.post("/api/v1/contents", headers=headers(author), json={"channel_id": channel_id, "title": "周末聚会", "body": "欢迎来", **extra})
    assert created.status_code == 200, created.text
    approve(client, author, created.json()["content_id"])
    return created.json()["content_id"]


def _notes(client, token: str, kind: str) -> list[dict]:
    return [item for item in client.get("/api/v1/me/notifications", headers=headers(token)).json()["items"] if item["kind"] == kind]


def test_reply_notifies_the_author_only_once_public_and_is_capped_per_hour(client, monkeypatch):
    author = register(client, "reply-author@example.com", "作者")
    verify(client, author, "+447700900901")
    replier = register(client, "replier@example.com", "加微信 abc 低价")
    url = f"/api/v1/contents/{_published_post(client, author, housing_channel(client))}/comments"

    first = client.post(url, headers=headers(replier), json={"body": "第一条"}).json()
    assert first["status"] == "pending"  # 留言默认要审
    assert _notes(client, author, "reply") == []  # 没过审：不能先把回复者的名字推给作者
    done = client.post(f"/api/v1/moderation/comments/{first['comment_id']}/decision", headers=headers(author), json={"decision": "approve"})
    assert done.status_code == 200, done.text
    assert len(_notes(client, author, "reply")) == 1

    monkeypatch.setattr(contents, "HOURLY_REPLY_LIMIT", 2)
    assert client.post(url, headers=headers(replier), json={"body": "第二条"}).status_code == 200
    assert client.post(url, headers=headers(replier), json={"body": "第三条"}).status_code == 429


def test_posts_outside_any_channel_can_be_replied_to(client):
    """发到「我的动态」的帖子不在任何频道里：原来回复接口直接说「内容不存在」。"""
    author = register(client, "profile-author@example.com")
    verify(client, author, "+447700900909")
    replier = register(client, "profile-replier@example.com")
    post = client.post("/api/v1/contents", headers=headers(author), json={"title": "只发在我的动态", "body": "没有选频道"}).json()
    approve(client, author, post["content_id"])
    url = f"/api/v1/contents/{post['content_id']}/comments"

    reply = client.post(url, headers=headers(replier), json={"body": "能回复了"})
    assert reply.status_code == 200, reply.text
    done = client.post(f"/api/v1/moderation/comments/{reply.json()['comment_id']}/decision", headers=headers(author), json={"decision": "approve"})
    assert done.status_code == 200, done.text
    assert [item["body"] for item in client.get(url).json()["items"]] == ["能回复了"]
    assert len(_notes(client, author, "reply")) == 1


def test_reports_are_rate_limited(client):
    target = _me(client, register(client, "reported@example.com"))
    for _ in range(10):
        assert client.post(f"/api/v1/users/{target}/report", json={"reason": "scam"}).status_code == 200
    assert client.post(f"/api/v1/users/{target}/report", json={"reason": "scam"}).status_code == 429


def test_deleting_a_post_takes_its_image_offline(client):
    author = register(client, "photo-author@example.com")
    verify(client, author, "+447700900902")
    key = client.post("/api/v1/uploads/sign", headers=headers(author), json={"content_type": "image/png"}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(author), content=b"\x89PNG").status_code == 200
    content_id = _published_post(client, author, housing_channel(client), image_keys=[key])
    assert client.get(f"/api/v1/uploads/{key}").status_code == 200
    assert client.delete(f"/api/v1/contents/{content_id}", headers=headers(author)).status_code == 200
    assert client.get(f"/api/v1/uploads/{key}").status_code == 404


def test_export_is_complete_and_erasing_wipes_the_text(client):
    boss = register_admin(client, "boss@example.com", admin=True)
    author = register(client, "leaving@example.com")
    verify(client, author, "+447700900903")
    channel_id = housing_channel(client)
    content_id = _published_post(client, author, channel_id)
    client.post(f"/api/v1/contents/{content_id}/comments", headers=headers(author), json={"body": "我的电话 07700 900000"})
    listing = client.post(
        "/api/v1/listings",
        headers=headers(author),
        json={"channel_id": channel_id, "title": "单间出租", "body": "近地铁", "category": "房产", "kind": "rent", "area": "Zone 2",
              "price_amount": "900", "price_unit": "月", "contact": "微信 leaving123"},
    )
    assert listing.status_code == 200, listing.text
    # 「我的帖子」带上类型和是否结案，页面据此显示「续期 / 结案」
    mine = {post["title"]: (post["type"], post["closed"]) for post in client.get("/api/v1/me/posts", headers=headers(author)).json()["items"]}
    assert mine == {"周末聚会": ("post", False), "单间出租": ("listing", False)}

    export = client.get(f"/api/v1/admin/users/{_me(client, author)}/export", headers=headers(boss)).json()
    assert {post["body"] for post in export["posts"]} == {"欢迎来", "近地铁"}
    assert "微信 leaving123" in {post["contact"] for post in export["posts"]}
    assert [row["body"] for row in export["comments"]] == ["我的电话 07700 900000"]

    assert client.delete("/api/v1/me", headers=headers(author)).status_code == 200
    with client.session_factory() as session:
        post = session.get(Content, content_id)
        assert (post.title, post.body, post.summary) == ("已注销用户的内容", None, None)
        assert session.get(ListingExt, listing.json()["content_id"]).contact == ""
        assert session.query(RoomComment).filter_by(content_id=content_id).one().body == ""


def test_room_submissions_stay_out_of_the_admin_queue(client):
    boss = register_admin(client, "queue-boss@example.com", admin=True)
    owner = register(client, "queue-owner@example.com")
    verify(client, owner, "+447700900904")
    member = register(client, "queue-member@example.com")
    verify(client, member, "+447700900905")
    submission = _post(client, member, _live_room(client, owner), "成员投稿")
    newcomer = client.post("/api/v1/contents", headers=headers(member), json={"title": "新用户的帖子", "body": "发到个人动态"}).json()
    assert (submission["status"], newcomer["status"]) == ("pending", "pending")

    waiting = {item["content_id"] for item in client.get("/api/v1/admin/queue", headers=headers(boss)).json()["contents"]}
    assert newcomer["content_id"] in waiting
    assert submission["content_id"] not in waiting  # 归房主审；管理员点「通过」会绕过房主


def test_reapproving_a_hidden_post_does_not_bump_it(client):
    author = register(client, "old-post@example.com")
    verify(client, author, "+447700900906")
    content_id = _published_post(client, author, housing_channel(client))
    with client.session_factory() as session:
        before = session.query(ChannelItem).filter_by(content_id=content_id).one().added_at
        session.get(Content, content_id).status = "pending"  # 被多人举报后自动隐藏的状态：公开过，等复核
        session.commit()
    approve(client, author, content_id)
    with client.session_factory() as session:
        assert session.query(ChannelItem).filter_by(content_id=content_id).one().added_at == before


def test_wrong_passwords_from_elsewhere_do_not_lock_the_owner_out(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "trust_proxy", True)
    register(client, "victim@example.com")

    def login(password: str, ip: str):
        return client.post("/api/v1/auth/login", json={"email": "victim@example.com", "password": password}, headers={"X-Forwarded-For": ip})

    for _ in range(10):
        assert login("wrong-password", "203.0.113.7").status_code == 401
    assert login("wrong-password", "203.0.113.7").status_code == 429
    assert login("password-1", "198.51.100.9").status_code == 200  # 本人在别处照常登录


def test_videos_have_their_own_daily_cap(client, monkeypatch):
    monkeypatch.setattr(uploads, "DAILY_VIDEO_SLOTS", 1)
    user = register(client, "video-uploader@example.com")

    def sign(content_type: str) -> int:
        return client.post("/api/v1/uploads/sign", headers=headers(user), json={"content_type": content_type}).status_code

    assert (sign("video/mp4"), sign("video/mp4"), sign("image/png")) == (200, 429, 200)


def test_super_admin_needs_two_factor_outside_dev(client, monkeypatch):
    boss = register_admin(client, "no-2fa@example.com", admin=True)
    assert client.get("/api/v1/admin/export/users", headers=headers(boss)).status_code == 200  # 开发环境不强制
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    refused = client.get("/api/v1/admin/export/users", headers=headers(boss))
    assert (refused.status_code, refused.json()["code"]) == (403, "TOTP_SETUP_REQUIRED")
    assert client.get("/api/v1/admin/me", headers=headers(boss)).status_code == 200  # 还能进后台去开两步验证


def test_reading_the_feed_clears_unread_marks(client):
    author = register(client, "feed-author@example.com")
    verify(client, author, "+447700900907")
    reader = register(client, "feed-reader@example.com")
    channel_id = housing_channel(client)
    assert client.put(f"/api/v1/me/subscriptions/{channel_id}", headers=headers(reader)).status_code == 200
    _published_post(client, author, channel_id)

    def unread() -> list[bool]:
        return [item["is_unread"] for item in client.get("/api/v1/me/feed", headers=headers(reader)).json()["items"]]

    assert unread() == [True]
    assert client.post("/api/v1/me/feed/seen", headers=headers(reader)).status_code == 200
    assert unread() == [False]


def test_admin_cannot_revive_a_post_its_author_deleted(client):
    boss = register_admin(client, "restore-boss@example.com", admin=True)
    author = register(client, "restore-author@example.com")
    verify(client, author, "+447700900908")
    content_id = _published_post(client, author, housing_channel(client))

    def status(action: str) -> int:
        return client.post(f"/api/v1/admin/contents/{content_id}/status", headers=headers(boss), json={"action": action}).status_code

    assert (status("remove"), status("restore")) == (200, 200)  # 管理员下架的可以恢复
    assert client.delete(f"/api/v1/contents/{content_id}", headers=headers(author)).status_code == 200
    assert status("restore") == 409  # 作者自己删的不行，哪怕以前被下架过一次


def test_oversized_fields_are_rejected_before_the_database(client):
    user = register(client, "long-fields@example.com")
    assert client.post("/api/v1/me/regions", headers=headers(user), json={"region_code": "UK", "source": "x" * 40}).status_code == 422
    long_consent = [{"purpose": "p" * 60, "version": "1", "granted": True}]
    refused = client.post(
        "/api/v1/auth/register", json={"email": "long@example.com", "password": "password-1", "display_name": "长", "consents": long_consent}
    )
    assert refused.status_code == 422

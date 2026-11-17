"""白名单用户：帖子 / 评论 / 视频不等人工审核（敏感词照拦），建房不受数量上限；只有超级管理员能设。"""
from sqlalchemy import select

from app.models import AuditLog, BlockedTerm, User
from tests.test_admin import admin_login, register as register_admin
from tests.test_rooms import headers, official_channel, register, upload, verify


def _trust(client, boss: str, email: str, on: bool = True):
    with client.session_factory() as session:
        user_id = session.scalar(select(User.id).where(User.email == email))
    return client.post(f"/api/v1/admin/users/{user_id}/trusted", headers=headers(boss), json={"is_trusted": on, "reason": "老用户"})


def _post(client, token: str, channel_id: str, **extra) -> dict:
    response = client.post("/api/v1/contents", headers=headers(token), json={"channel_id": channel_id, "title": "标题", "body": "正文", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_only_super_admin_sets_trusted_and_it_is_audited(client):
    boss = register_admin(client, "trust-boss@example.com", admin=True)
    register(client, "trust-target@example.com")
    register_admin(client, "trust-mod@example.com")
    with client.session_factory() as session:
        mod = session.scalar(select(User).where(User.email == "trust-mod@example.com"))
        mod.is_admin = True
        session.commit()
    moderator = admin_login(client, "trust-mod@example.com")

    assert _trust(client, moderator, "trust-target@example.com").status_code == 403
    done = _trust(client, boss, "trust-target@example.com")
    assert done.status_code == 200, done.text
    assert done.json()["is_trusted"] is True
    assert _trust(client, boss, "trust-target@example.com").status_code == 409  # 已经是
    assert _trust(client, boss, "trust-target@example.com", on=False).json()["is_trusted"] is False
    with client.session_factory() as session:
        actions = session.scalars(select(AuditLog.action).where(AuditLog.action.like("admin.user.%trust")).order_by(AuditLog.created_at)).all()
    assert actions == ["admin.user.trust", "admin.user.untrust"]


def test_trusted_user_skips_review_but_not_blocked_terms(client):
    boss = register_admin(client, "trust-boss2@example.com", admin=True)
    channel_id = official_channel(client)
    plain = register(client, "plain@example.com")
    verify(client, plain, "+447700900401")
    trusted = register(client, "trusted@example.com")
    verify(client, trusted, "+447700900402")
    assert _trust(client, boss, "trusted@example.com").status_code == 200

    # 普通新用户：前几条帖子、评论都要等审核
    assert _post(client, plain, channel_id)["status"] == "pending"
    # 白名单：帖子、视频、评论直接发布
    post = _post(client, trusted, channel_id)
    assert post["status"] == "published"
    clip = upload(client, trusted, "video/mp4", b"\x00\x00\x00\x18ftypmp42")
    assert _post(client, trusted, channel_id, post_type="video", video_key=clip, rights_confirmed=True)["status"] == "published"
    reply = client.post(f"/api/v1/contents/{post['content_id']}/comments", headers=headers(trusted), json={"body": "补充一句"})
    assert reply.json()["status"] == "published", reply.text
    other = client.post(f"/api/v1/contents/{post['content_id']}/comments", headers=headers(plain), json={"body": "路过"})
    assert other.json()["status"] == "pending", other.text

    # 敏感词照拦
    with client.session_factory() as session:
        session.add(BlockedTerm(term="违禁词"))
        session.commit()
    assert _post(client, trusted, channel_id, body="含违禁词")["status"] == "pending"
    blocked = client.post(f"/api/v1/contents/{post['content_id']}/comments", headers=headers(trusted), json={"body": "违禁词"})
    assert blocked.json()["status"] == "pending"


def test_trusted_room_comment_published_directly(client):
    boss = register_admin(client, "trust-boss3@example.com", admin=True)
    owner = register(client, "trust-room-owner@example.com")
    verify(client, owner, "+447700900403")
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "白名单房间", "parent_channel_id": official_channel(client)}).json()["channel_id"]
    assert client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"}).status_code == 200
    guest = register(client, "trust-room-guest@example.com")
    verify(client, guest, "+447700900404")

    first = client.post(f"/api/v1/channels/{room_id}/comments", headers=headers(guest), json={"body": "第一条留言"})
    assert first.json()["status"] == "pending", first.text
    assert _trust(client, boss, "trust-room-guest@example.com").status_code == 200
    second = client.post(f"/api/v1/channels/{room_id}/comments", headers=headers(guest), json={"body": "第二条留言"})
    assert second.json()["status"] == "published", second.text


def test_trusted_user_not_limited_by_room_count(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.channels.ROOM_LIMIT", 1)
    boss = register_admin(client, "trust-boss4@example.com", admin=True)
    owner = register(client, "trust-many-rooms@example.com")
    verify(client, owner, "+447700900405")
    parent_id = official_channel(client)

    def create(name: str):
        return client.post("/api/v1/channels", headers=headers(owner), json={"name": name, "parent_channel_id": parent_id})

    assert create("一号房").status_code == 200
    assert create("二号房").json()["code"] == "CHANNEL_LIMIT"
    assert _trust(client, boss, "trust-many-rooms@example.com").status_code == 200
    assert create("二号房").status_code == 200

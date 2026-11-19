"""后台「AI 判断是否广告号」：只给管理员用、把最近的帖子交给 AI、结果原样带回并记操作日志；没帖子 / AI 不可用时报错，不动账号。"""
from sqlalchemy import select

import app.llm as llm
from app.api.v1.admin import AccountVerdict
from app.models import AuditLog, Channel, ChannelItem, Content, User
from tests.test_news import make_admin
from tests.test_rooms import headers, register


def seed_posts(client, email: str) -> str:
    session = client.session_factory()
    user = session.scalar(select(User).where(User.email == email))
    channel = Channel(code="uk-housing-t", name_hans="英国房产", name_hant="英國房產", kind="official_curated", region_code="UK", is_active=True)
    session.add(channel)
    session.flush()
    for n in range(3):
        post = Content(type="post", status="published", title=f"伦敦东区单间出租 {n}", summary="加微信 abc123 看房", author_id=user.id)
        session.add(post)
        session.flush()
        session.add(ChannelItem(channel_id=channel.id, content_id=post.id))
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def test_ai_check_user(client, monkeypatch):
    register(client, "spammer@example.com")
    target = seed_posts(client, "spammer@example.com")
    sent = {}

    def fake_ask(system, prompt, schema, shape):
        sent.update(prompt=prompt, schema=schema)
        return AccountVerdict(verdict="agency_batch", reasons=["标题模板化", "都留同一个微信号", "a", "b", "c"])

    monkeypatch.setattr(llm, "ask_json", fake_ask)

    user_token = register(client, "plain@example.com")
    assert client.post(f"/api/v1/admin/users/{target}/ai-check", headers=headers(user_token)).status_code == 403

    admin = make_admin(client, "ai-check-admin@example.com")
    response = client.post(f"/api/v1/admin/users/{target}/ai-check", headers=headers(admin))
    assert response.status_code == 200
    body = response.json()
    # 理由最多 4 条；帖子标题和所在频道都交给了 AI
    assert body == {"verdict": "agency_batch", "reasons": ["标题模板化", "都留同一个微信号", "a", "b"], "post_count": 3}
    assert "伦敦东区单间出租 0" in sent["prompt"] and "英国房产" in sent["prompt"] and sent["schema"] is AccountVerdict

    session = client.session_factory()
    log = session.scalar(select(AuditLog).where(AuditLog.action == "admin.user.ai_check"))
    assert log is not None and log.target_id == target
    # 只是建议：账号状态不变
    assert session.get(User, target).status == "active"
    session.close()

    # AI 不可用：报 503，不出结果
    def down(*args):
        raise llm.LLMUnavailable("还没有配置 AI 密钥")

    monkeypatch.setattr(llm, "ask_json", down)
    failed = client.post(f"/api/v1/admin/users/{target}/ai-check", headers=headers(admin))
    assert failed.status_code == 503 and failed.json()["code"] == "AI_UNAVAILABLE"

    # 没发过东西的人没法判断
    register(client, "quiet@example.com")
    session = client.session_factory()
    quiet = session.scalar(select(User.id).where(User.email == "quiet@example.com"))
    session.close()
    assert client.post(f"/api/v1/admin/users/{quiet}/ai-check", headers=headers(admin)).json()["code"] == "NO_POSTS"

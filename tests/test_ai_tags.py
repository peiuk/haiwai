"""发帖后 AI 补关键词、建议换频道：用户填的关键词不动；只看官方频道里的普通帖子；管理员确认才移，并通知作者。"""
from sqlalchemy import select

import app.ai_tags as ai
from app.models import Channel, ChannelItem, Content, Notification, User
from tests.test_h5_domain import headers, register, verify
from tests.test_news import make_admin


def channels(client) -> dict[str, str]:
    session = client.session_factory()
    rows = {
        "chat": Channel(code="uk-chat", name_hans="英国交流", name_hant="英國交流", kind="official_curated", category="交流", region_code="UK", is_active=True),
        "housing": Channel(code="uk-housing", name_hans="英国房产", name_hant="英國房產", kind="official_curated", category="房产", region_code="UK", is_active=True),
        "news": Channel(code="uk-news", name_hans="英国资讯", name_hant="英國資訊", kind="official_auto", category="资讯", region_code="UK", is_active=True),
    }
    session.add_all(rows.values())
    session.commit()
    ids = {key: channel.id for key, channel in rows.items()}
    session.close()
    return ids


def post(client, token: str, channel_id: str, **extra) -> str:
    created = client.post("/api/v1/contents", headers=headers(token), json={"channel_id": channel_id, "title": "伦敦东区单间出租", "body": "近地铁，月租 900 镑", **extra})
    assert created.status_code == 200, created.text
    return created.json()["content_id"]


def test_post_gets_ai_keywords_and_channel_suggestion(client, monkeypatch):
    ids = channels(client)
    token = register(client, "renter@example.com")
    verify(client, token, "+447700900101")
    prompts: list[str] = []

    def fake_ask(prompt):
        prompts.append(prompt)
        # 带 # 的去掉、有空格的 / 太长的丢掉、和城市话题重复的丢掉
        return ai.Verdict(keywords=["#租房", "伦敦", "有 空格", "超过十二个字的关键词不要了吧", "英国"], channel_index=1, reason="这是租房信息")

    monkeypatch.setattr(ai, "ask_ai", fake_ask)
    content_id = post(client, token, ids["chat"], city_topic="伦敦")  # TestClient 等后台任务跑完才返回

    assert "[0] 英国交流（现在的频道）" in prompts[0] and "[1] 英国房产" in prompts[0] and "英国资讯" not in prompts[0]
    session = client.session_factory()
    content = session.get(Content, content_id)
    assert content.keyword_source == "ai_auto" and content.keywords_json == '["租房", "英国"]'
    assert content.ai_channel_id == ids["housing"] and content.ai_channel_reason == "这是租房信息"
    assert content.body == "近地铁，月租 900 镑"  # 正文不动
    session.close()


def test_user_keywords_are_kept_and_right_channel_clears_suggestion(client, monkeypatch):
    ids = channels(client)
    token = register(client, "tagger@example.com")
    verify(client, token, "+447700900102")
    monkeypatch.setattr(ai, "ask_ai", lambda prompt: ai.Verdict(keywords=["别的词"], channel_index=0))
    content_id = post(client, token, ids["chat"], keywords=["自己填的"])
    session = client.session_factory()
    content = session.get(Content, content_id)
    assert content.keywords_json == '["自己填的"]' and content.keyword_source == "user"
    assert content.ai_channel_id is None
    session.close()


def test_without_ai_key_post_still_works(client):
    ids = channels(client)
    token = register(client, "nokey@example.com")
    verify(client, token, "+447700900103")
    content_id = post(client, token, ids["chat"], body="想找人合租")  # 测试里没有 AI 密钥：用词表补的关键词
    session = client.session_factory()
    content = session.get(Content, content_id)
    assert content.keyword_source == "ai_auto" and "合租" in content.keywords_json and content.ai_channel_id is None
    session.close()


def test_admin_moves_or_dismisses_suggestion(client, monkeypatch):
    ids = channels(client)
    token = register(client, "mover@example.com")
    verify(client, token, "+447700900104")
    monkeypatch.setattr(ai, "ask_ai", lambda prompt: ai.Verdict(keywords=[], channel_index=1, reason="租房帖"))
    first = post(client, token, ids["chat"])
    second = post(client, token, ids["chat"])
    admin = headers(make_admin(client, "ai-channel-boss@example.com"))
    url = "/api/v1/admin/contents/{}/ai-channel"

    listed = {row["content_id"]: row for row in client.get("/api/v1/admin/contents?type=post", headers=admin).json()["items"]}
    assert listed[first]["ai_channel"] == {"name": "英国房产", "reason": "租房帖"}
    assert client.post(url.format(first), headers=headers(token), json={"action": "move"}).status_code in (401, 403)

    assert client.post(url.format(first), headers=admin, json={"action": "move"}).json()["moved"] is True
    assert client.post(url.format(second), headers=admin, json={"action": "dismiss"}).json()["moved"] is False
    assert client.post(url.format(first), headers=admin, json={"action": "move"}).status_code == 404  # 已经处理过

    session = client.session_factory()
    assert session.scalars(select(ChannelItem.channel_id).where(ChannelItem.content_id == first)).all() == [ids["housing"]]
    assert session.scalars(select(ChannelItem.channel_id).where(ChannelItem.content_id == second)).all() == [ids["chat"]]
    assert session.get(Content, first).ai_channel_id is None and session.get(Content, second).ai_channel_id is None
    author = session.scalar(select(User).where(User.email == "mover@example.com"))
    notes = session.scalars(select(Notification.body).where(Notification.user_id == author.id, Notification.content_id == first)).all()
    assert any("已移到「英国房产」" in note for note in notes)
    session.close()

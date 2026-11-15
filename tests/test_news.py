"""每日 AI 资讯：只收相关的、数字对不上标待核对、全部待审、发布后才出现、重跑不重复、没密钥不写任何东西。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import app.news as news
from app.models import Channel, ChannelItem, Content, User
from tests.test_rooms import headers, register

NOW = datetime.now(timezone.utc).isoformat()
OLD = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
ITEMS = [
    {"title": "Visa fee rises to £524", "description": "The fee goes up on 1 April.", "url": "https://www.gov.uk/n/visa", "published": NOW},
    {"title": "NHS waiting times", "description": "Waiting lists fell.", "url": "https://www.gov.uk/n/nhs", "published": NOW},
    {"title": "Minister visits Wales", "description": "A ministerial visit.", "url": "https://www.gov.uk/n/visit", "published": NOW},
    {"title": "Old story", "description": "Too old.", "url": "https://www.gov.uk/n/old", "published": OLD},
]


def fake_write(items):
    out = []
    for i, item in enumerate(items):
        if "Visa" in item["title"]:
            out.append(news.Draft(index=i, title_zh="签证费涨到524英镑", summary_zh="4月1日起上调。", relevant=True, topic="签证移民"))
        elif "NHS" in item["title"]:
            # 原文没有 30 这个数字：要标「待核对」
            out.append(news.Draft(index=i, title_zh="NHS 等候名单减少30%", summary_zh="等候名单下降。", relevant=True, topic="医疗健康"))
        else:
            out.append(news.Draft(index=i, title_zh="部长访问威尔士", summary_zh="礼节性访问。", relevant=False, topic="其他"))
    return out


def make_admin(client, email: str) -> str:
    token = register(client, email)
    session = client.session_factory()
    session.scalar(select(User).where(User.email == email)).is_admin = True
    session.commit()
    session.close()
    # 后台接口只认后台登录发的令牌
    return client.post("/api/v1/admin/login", json={"email": email, "password": "password-1"}).json()["access_token"]


def channels(client) -> dict[str, str]:
    session = client.session_factory()
    visa = Channel(code="uk-visa", name_hans="签证与政策", name_hant="簽證與政策", kind="official_auto", region_code="UK", is_active=True)
    news_ch = Channel(code="uk-news", name_hans="英国资讯", name_hant="英國資訊", kind="official_curated", region_code="UK", category="资讯", is_active=True)
    session.add_all([visa, news_ch])
    session.commit()
    ids = {"visa": visa.id, "news": news_ch.id}
    session.close()
    return ids


def test_next_run_is_8am_london_across_dst():
    # 冬令时（伦敦 = UTC）：7:00 UTC 起 1 小时后；9:00 UTC 起到第二天 8:00 是 23 小时
    assert news.seconds_until_next_run(datetime(2026, 11, 15, 7, 0, tzinfo=timezone.utc)) == 3600
    assert news.seconds_until_next_run(datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)) == 23 * 3600
    # 夏令时（伦敦 = UTC+1）：伦敦 8 点是 UTC 7 点
    assert news.seconds_until_next_run(datetime(2026, 7, 1, 6, 0, tzinfo=timezone.utc)) == 3600
    # 跨 10 月改时：周六伦敦 10 点（夏令时）到周日伦敦 8 点（冬令时）实际是 23 小时，不能早一小时
    assert news.seconds_until_next_run(datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)) == 23 * 3600


def test_numbers_match():
    assert news.numbers_match("fee £1,524 from 1 April", "费用1524英镑，4月1日起")
    assert not news.numbers_match("waiting lists fell", "减少30%")


def test_daily_news_drafts_wait_for_review(client):
    ids = channels(client)
    session = client.session_factory()
    result = news.run_daily_news(session, fetch=lambda: ITEMS, write=fake_write)
    session.close()
    # 太旧的那条不送去 AI；还没有通过的稿子，所以不出汇总帖
    assert result == {"fetched": 3, "drafted": 2, "skipped": 1, "to_check": 1, "digest": 0}

    session = client.session_factory()
    rows = session.scalars(select(Content).where(Content.source_name == "GOV.UK")).all()
    by_title = {row.title: row for row in rows}
    assert all(row.status == "pending" and row.type == "news" for row in rows)
    assert by_title["签证费涨到524英镑"].ai_status == "ok"
    assert by_title["NHS 等候名单减少30%"].ai_status == "check"
    visa_id = by_title["签证费涨到524英镑"].id
    # 签证类进签证频道，其余进资讯频道
    assert session.scalar(select(ChannelItem.channel_id).where(ChannelItem.content_id == visa_id)) == ids["visa"]
    nhs_id = by_title["NHS 等候名单减少30%"].id
    assert session.scalar(select(ChannelItem.channel_id).where(ChannelItem.content_id == nhs_id)) == ids["news"]
    session.close()

    # 审核通过前前台看不到，通过后出现
    assert client.get(f"/api/v1/channels/{ids['visa']}/items").json()["items"] == []
    token = make_admin(client, "news-admin@example.com")
    approved = client.post(f"/api/v1/moderation/{visa_id}/decision", headers=headers(token), json={"decision": "approve"})
    assert approved.status_code == 200
    assert [item["title"] for item in client.get(f"/api/v1/channels/{ids['visa']}/items").json()["items"]] == ["签证费涨到524英镑"]
    queue = client.get("/api/v1/admin/queue", headers=headers(token)).json()["contents"]
    flagged = next(row for row in queue if row["content_id"] == nhs_id)
    assert flagged["ai_draft"] and flagged["ai_check"] and flagged["source_url"] == "https://www.gov.uk/n/nhs"

    # 拒绝 NHS 那条；再跑一次：已生成的不重复，汇总帖只收通过的，被拒的不能混进去
    rejected = client.post(f"/api/v1/moderation/{nhs_id}/decision", headers=headers(token), json={"decision": "reject"})
    assert rejected.status_code == 200
    session = client.session_factory()
    again = news.run_daily_news(session, fetch=lambda: ITEMS, write=fake_write)
    assert again["drafted"] == 0 and again["digest"] == 1
    digest = session.scalar(select(Content).where(Content.type == "post", Content.source_name == "GOV.UK"))
    assert digest.status == "published" and digest.title.startswith("今日英国要闻")
    assert "https://www.gov.uk/n/visa" in digest.body and "https://www.gov.uk/n/nhs" not in digest.body
    # 同一天只出一篇
    assert news.run_daily_news(session, fetch=lambda: ITEMS, write=fake_write)["digest"] == 0
    session.close()


def test_mismatched_ai_items_write_nothing(client):
    channels(client)

    def skips_one(items):  # 漏掉第 0 条、编号顺延：摘要会配错链接，必须整批作废
        return [d.model_copy(update={"index": d.index - 1}) for d in fake_write(items)[1:]]

    session = client.session_factory()
    try:
        news.run_daily_news(session, fetch=lambda: ITEMS, write=skips_one)
        raise AssertionError("应当报 NewsUnavailable")
    except news.NewsUnavailable:
        pass
    assert session.scalar(select(Content).where(Content.source_name == "GOV.UK")) is None
    session.close()


def test_openai_compatible_provider(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_API_BASE", "https://llm.example.com/v1/")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    get_settings.cache_clear()
    sent = {}

    class Reply:
        def __init__(self, content: str):
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, auth=headers["Authorization"], model=json["model"], fmt=json["response_format"])
        return Reply('{"items":[{"index":0,"title_zh":"签证费上调","summary_zh":"4月1日起。","relevant":true,"topic":"签证移民"}]}')

    monkeypatch.setattr(news.httpx, "post", fake_post)
    drafts = news.write_drafts(ITEMS[:1])
    assert drafts[0].title_zh == "签证费上调" and drafts[0].topic == "签证移民"
    assert sent == {
        "url": "https://llm.example.com/v1/chat/completions",
        "auth": "Bearer test-key",
        "model": "some-model",
        "fmt": {"type": "json_object"},
    }
    # 返回不是约定的 JSON：报不可用，不写半截数据
    monkeypatch.setattr(news.httpx, "post", lambda url, headers, json, timeout: Reply("抱歉，我不能"))
    try:
        news.write_drafts(ITEMS[:1])
        raise AssertionError("应当报 NewsUnavailable")
    except news.NewsUnavailable:
        pass
    get_settings.cache_clear()


def test_endpoint_needs_admin_and_key(client, monkeypatch):
    channels(client)
    monkeypatch.setattr(news, "fetch_govuk", lambda: ITEMS)
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    token = register(client, "news-user@example.com")
    assert client.post("/api/v1/admin/ingest/news", headers=headers(token)).status_code == 403
    admin = make_admin(client, "news-boss@example.com")
    response = client.post("/api/v1/admin/ingest/news", headers=headers(admin))
    assert response.status_code == 503 and response.json()["code"] == "NEWS_UNAVAILABLE"
    session = client.session_factory()
    assert session.scalar(select(Content).where(Content.source_name == "GOV.UK")) is None  # 什么都没写
    session.close()
    get_settings.cache_clear()

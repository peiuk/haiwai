"""每日 AI 资讯：只收相关的、数字对不上标待核对、全部待审、发布后才出现、重跑不重复、没密钥不写任何东西。
英国的进英国资讯、国际的进国际新闻；BBC 稿署名 BBC；一个来源打不开不连累其他来源。"""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

import app.llm as llm
import app.news as news
from app.models import Channel, ChannelItem, Content, User
from tests.test_rooms import headers, register

NOW = datetime.now(timezone.utc).isoformat()
OLD = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
GOV = {"source": "GOV.UK", "licence": "OGL v3.0", "hint": "英国"}
ITEMS = [
    {"title": "Visa fee rises to £524", "description": "The fee goes up on 1 April.", "url": "https://www.gov.uk/n/visa", "published": NOW, **GOV},
    {"title": "NHS waiting times", "description": "Waiting lists fell.", "url": "https://www.gov.uk/n/nhs", "published": NOW, **GOV},
    {"title": "Minister visits Wales", "description": "A ministerial visit.", "url": "https://www.gov.uk/n/visit", "published": NOW, **GOV},
    {"title": "Old story", "description": "Too old.", "url": "https://www.gov.uk/n/old", "published": OLD, **GOV},
    {
        "title": "China and EU agree trade deal",
        "description": "Leaders met in Brussels.",
        "url": "https://www.bbc.co.uk/news/articles/world1",
        "published": NOW,
        "source": "BBC",
        "licence": "© BBC",
        "hint": "国际",
    },
]


def fake_write(items):
    out = []
    for i, item in enumerate(items):
        if "Visa" in item["title"]:
            out.append(news.Draft(index=i, title_zh="签证费涨到524英镑", summary_zh="4月1日起上调。", relevant=True, scope="uk"))
        elif "NHS" in item["title"]:
            # 原文没有 30 这个数字：要标「待核对」
            out.append(news.Draft(index=i, title_zh="NHS 等候名单减少30%", summary_zh="等候名单下降。", relevant=True, scope="uk"))
        elif "China" in item["title"]:
            out.append(news.Draft(index=i, title_zh="中欧达成贸易协议", summary_zh="双方领导人在布鲁塞尔会面。", relevant=True, scope="international"))
        else:
            out.append(news.Draft(index=i, title_zh="部长访问威尔士", summary_zh="礼节性访问。", relevant=False, scope="uk"))
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
    # 老的签证频道还在也不该再收资讯：签证政策统一进英国资讯
    visa = Channel(code="uk-visa", name_hans="签证与政策", name_hant="簽證與政策", kind="official_auto", region_code="UK", is_active=True)
    news_ch = Channel(code="uk-news", name_hans="英国资讯", name_hant="英國資訊", kind="official_curated", region_code="UK", category="资讯", is_active=True)
    world = Channel(code="global-news", name_hans="新闻", name_hant="新聞", kind="official_curated", region_code="GLOBAL", category="新闻", is_active=True)
    session.add_all([visa, news_ch, world])
    session.commit()
    ids = {"visa": visa.id, "news": news_ch.id, "world": world.id}
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
    assert result == {"fetched": 4, "drafted": 3, "skipped": 1, "to_check": 1, "digest": 0}

    session = client.session_factory()
    rows = session.scalars(select(Content).where(Content.type == "news")).all()
    by_title = {row.title: row for row in rows}
    assert all(row.status == "pending" for row in rows)
    assert by_title["签证费涨到524英镑"].ai_status == "ok"
    assert by_title["NHS 等候名单减少30%"].ai_status == "check"
    visa_id = by_title["签证费涨到524英镑"].id
    nhs_id = by_title["NHS 等候名单减少30%"].id
    world_row = by_title["中欧达成贸易协议"]
    # BBC 稿署名 BBC，不能写成 GOV.UK 的开放许可
    assert (world_row.source_name, world_row.licence_ref) == ("BBC", "© BBC")
    assert (by_title["签证费涨到524英镑"].source_name, by_title["签证费涨到524英镑"].licence_ref) == ("GOV.UK", "OGL v3.0")
    # 英国的（含签证政策）进英国资讯，国际的进国际新闻；老签证频道不再收
    channel_of = lambda content_id: session.scalar(select(ChannelItem.channel_id).where(ChannelItem.content_id == content_id))  # noqa: E731
    assert channel_of(visa_id) == ids["news"] and channel_of(nhs_id) == ids["news"]
    assert channel_of(world_row.id) == ids["world"]
    session.close()

    # 审核通过前前台看不到，通过后出现
    assert client.get(f"/api/v1/channels/{ids['news']}/items").json()["items"] == []
    token = make_admin(client, "news-admin@example.com")
    approved = client.post(f"/api/v1/moderation/{visa_id}/decision", headers=headers(token), json={"decision": "approve"})
    assert approved.status_code == 200
    assert [item["title"] for item in client.get(f"/api/v1/channels/{ids['news']}/items").json()["items"]] == ["签证费涨到524英镑"]
    queue = client.get("/api/v1/admin/queue", headers=headers(token)).json()["contents"]
    flagged = next(row for row in queue if row["content_id"] == nhs_id)
    assert flagged["ai_draft"] and flagged["ai_check"] and flagged["source_url"] == "https://www.gov.uk/n/nhs"
    assert next(row for row in queue if row["content_id"] == world_row.id)["ai_draft"]

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
    assert session.scalar(select(Content).where(Content.type == "news")) is None
    session.close()


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>BBC News</title>
<item><title>Visa rules change</title><description>Home Office update.</description>
<link>https://www.bbc.co.uk/news/articles/abc?at_medium=RSS&amp;at_campaign=rss</link>
<pubDate>Wed, 19 Nov 2026 08:00:00 GMT</pubDate></item>
<item><title></title><link>https://www.bbc.co.uk/news/empty</link></item>
</channel></rss>"""


class FakeResponse:
    def __init__(self, content: bytes = b"", status: int = 200):
        self.content = content
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise httpx.HTTPStatusError("boom", request=httpx.Request("GET", "https://x"), response=httpx.Response(self.status))


def test_fetch_bbc_parses_rss(monkeypatch):
    monkeypatch.setattr(news.httpx, "get", lambda url, timeout, follow_redirects: FakeResponse(RSS))
    items = news.fetch_bbc()
    # 英国、国际两个源各一条（同一份假数据）；没标题的跳过；追踪参数去掉；RFC 822 时间换成 ISO
    assert [item["hint"] for item in items] == ["英国", "国际"]
    first = items[0]
    assert first["url"] == "https://www.bbc.co.uk/news/articles/abc"
    assert first["source"] == "BBC" and first["licence"] == "© BBC"
    assert news._parse_time(first["published"]) == datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)


def test_one_source_down_does_not_block_others(monkeypatch):
    def govuk_down():
        raise news.NewsUnavailable("GOV.UK 暂时打不开")

    monkeypatch.setattr(news, "fetch_govuk", govuk_down)
    monkeypatch.setattr(news, "fetch_bbc", lambda: ITEMS[-1:])
    assert news.fetch_all() == ITEMS[-1:]
    # 全都打不开才算这次没有
    monkeypatch.setattr(news, "fetch_bbc", govuk_down)
    try:
        news.fetch_all()
        raise AssertionError("应当报 NewsUnavailable")
    except news.NewsUnavailable:
        pass


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
        return Reply('{"items":[{"index":0,"title_zh":"签证费上调","summary_zh":"4月1日起。","relevant":true,"scope":"uk"}]}')

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    drafts = news.write_drafts(ITEMS[:1])
    assert drafts[0].title_zh == "签证费上调" and drafts[0].scope == "uk"
    assert sent == {
        "url": "https://llm.example.com/v1/chat/completions",
        "auth": "Bearer test-key",
        "model": "some-model",
        "fmt": {"type": "json_object"},
    }
    # 返回不是约定的 JSON：报不可用，不写半截数据
    monkeypatch.setattr(llm.httpx, "post", lambda url, headers, json, timeout: Reply("抱歉，我不能"))
    try:
        news.write_drafts(ITEMS[:1])
        raise AssertionError("应当报 NewsUnavailable")
    except news.NewsUnavailable:
        pass
    get_settings.cache_clear()


def test_endpoint_needs_admin_and_key(client, monkeypatch):
    channels(client)
    monkeypatch.setattr(news, "fetch_govuk", lambda: ITEMS[:4])
    monkeypatch.setattr(news, "fetch_bbc", lambda: ITEMS[4:])
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    token = register(client, "news-user@example.com")
    assert client.post("/api/v1/admin/ingest/news", headers=headers(token)).status_code == 403
    admin = make_admin(client, "news-boss@example.com")
    response = client.post("/api/v1/admin/ingest/news", headers=headers(admin))
    assert response.status_code == 503 and response.json()["code"] == "NEWS_UNAVAILABLE"
    session = client.session_factory()
    assert session.scalar(select(Content).where(Content.type == "news")) is None  # 什么都没写
    session.close()
    get_settings.cache_clear()

"""发现页内容流：同一内容挂多个频道只出现一次；游标翻页不重复不遗漏；分类信息跟随筛选。"""
from datetime import datetime, timedelta, timezone

from app.models import Channel, ChannelItem, Content

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def global_channel(session, code: str, category: str) -> str:
    channel = Channel(code=code, name_hans=code, name_hant=code, kind="official_curated", category=category, region_code="GLOBAL", is_active=True)
    session.add(channel)
    session.flush()
    return channel.id


def seed(client) -> dict[str, object]:
    """两个国际频道；c0 同时挂在两个频道里（重复收录），c0–c4 按时间从新到旧。"""
    session = client.session_factory()
    life = global_channel(session, "g-life", "生活")
    housing = global_channel(session, "g-housing", "房产")
    now = datetime.now(timezone.utc)
    ids = []
    for index in range(5):
        content = Content(
            type="news",
            status="published",
            title=f"内容{index}",
            summary="摘要",
            source_name="测试",
            licence_ref="OGL v3.0",
            canonical_url=f"https://example.com/news/{index}",
            published_at=now,
        )
        session.add(content)
        session.flush()
        ids.append(content.id)
        session.add(ChannelItem(channel_id=life, content_id=content.id, added_at=now - timedelta(minutes=index)))
    session.add(ChannelItem(channel_id=housing, content_id=ids[0], added_at=now - timedelta(minutes=30)))
    session.commit()
    session.close()
    return {"ids": ids, "housing": housing}


def test_same_content_in_two_channels_appears_once(client):
    data = seed(client)
    items = client.get("/api/v1/discover/items").json()["items"]
    content_ids = [item["content_id"] for item in items]
    assert sorted(content_ids) == sorted(data["ids"])
    assert len(content_ids) == len(set(content_ids))
    # 取的是最新那次收录（生活频道），不是较早的房产频道
    first = next(item for item in items if item["content_id"] == data["ids"][0])
    assert first["channel_name"] == "g-life"
    # 只看房产时，这条内容以房产频道的收录出现
    housing_only = client.get("/api/v1/discover/items", params={"category": "房产"}).json()["items"]
    assert [item["content_id"] for item in housing_only] == [data["ids"][0]]


def test_cursor_pages_cover_everything_once_in_order(client):
    data = seed(client)
    seen: list[str] = []
    cursor = None
    for _ in range(10):
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = client.get("/api/v1/discover/items", params=params).json()
        seen += [item["content_id"] for item in body["items"]]
        cursor = body.get("next_cursor")
        if not cursor:
            break
    assert seen == data["ids"]  # 从新到旧，每条一次
    assert client.get("/api/v1/discover/items", params={"cursor": "not-a-cursor"}).status_code == 200


def test_guest_for_you_is_ranked_and_honest(client):
    data = seed(client)
    body = client.get("/api/v1/me/feed", params={"tab": "foryou", "limit": 3}).json()
    assert len(body["items"]) == 3 and body.get("next_cursor")
    # 游客没有「你的国家 / 你加入的频道」，理由不能这么写
    assert all(item["reason_code"] in {"activity", "curated"} for item in body["items"])
    assert {item["content_id"] for item in body["items"]} <= set(data["ids"])
    # 关注流仍然要登录
    assert client.get("/api/v1/me/feed").status_code == 401
    # 同时挂在私密房间里的内容，游客的推荐里不能出现
    session = client.session_factory()
    room = Channel(code="secret-room", name_hans="私密", name_hant="私密", kind="room", region_code="GLOBAL", is_active=True, is_private=True)
    session.add(room)
    session.flush()
    session.add(ChannelItem(channel_id=room.id, content_id=data["ids"][1]))
    session.commit()
    session.close()
    everything = client.get("/api/v1/me/feed", params={"tab": "foryou", "limit": 50}).json()["items"]
    assert {item["content_id"] for item in everything} == set(data["ids"]) - {data["ids"][1]}


def test_listings_follow_category_filter(client):
    token = client.post(
        "/api/v1/auth/register",
        json={"email": "lister-d@example.com", "password": "password-1", "display_name": "房东", "consents": CONSENTS},
    ).json()["access_token"]
    client.post("/api/v1/auth/verify-phone", headers=headers(token), json={"phone": "+447700900611", "code": "246810"})
    session = client.session_factory()
    housing = global_channel(session, "g-housing-l", "房产")
    global_channel(session, "g-jobs-l", "招聘")
    session.commit()
    session.close()
    created = client.post(
        "/api/v1/listings",
        headers=headers(token),
        json={
            "channel_id": housing,
            "title": "一居出租",
            "body": "整租一居，可看房",
            "category": "房产",
            "kind": "rent",
            "area": "伦敦",
            "price_amount": "1500",
            "price_unit": "月",
            "contact": "sms: 1",
            "attrs": {},
        },
    )
    assert created.status_code == 200, created.text
    content_id = created.json()["content_id"]
    client.post(f"/api/v1/moderation/{content_id}/decision", headers=headers(token), json={"decision": "approve"})

    def titles(**params):
        return [item["title"] for item in client.get("/api/v1/discover/listings", params=params).json()["items"]]

    assert titles() == ["一居出租"]
    assert titles(category="房产") == ["一居出租"]
    assert titles(category="招聘") == []  # 原来会照样显示房源
    assert titles(region="GLOBAL") == ["一居出租"]

    # 分类信息和频道动态合在一个内容流里，带上卡片字段；过期后不再出现
    def feed():
        return client.get("/api/v1/discover/items", params={"category": "房产"}).json()["items"]

    assert [item["content_id"] for item in feed()] == [content_id]
    assert feed()[0]["listing"]["price_amount"] == "1500"
    session = client.session_factory()
    session.get(Content, content_id).expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    session.commit()
    session.close()
    assert feed() == []


def test_guest_region_header_scopes_guest_content(client):
    """游客在首页选了国家（X-Region 头），发现页和推荐要给这个国家的内容；乱填的国家按国际处理。"""
    session = client.session_factory()
    uk = Channel(code="uk-life", name_hans="英国生活", name_hant="英國生活", kind="official_curated", category="生活", region_code="UK", is_active=True)
    session.add(uk)
    session.flush()
    content = Content(type="news", status="published", title="英国本地新闻", summary="摘要", source_name="测试",
                      licence_ref="OGL v3.0", canonical_url="https://example.com/uk", published_at=datetime.now(timezone.utc))
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=uk.id, content_id=content.id, added_at=datetime.now(timezone.utc)))
    session.commit()
    content_id = content.id
    session.close()

    def discover_ids(extra: dict[str, str]) -> set[str]:
        items = client.get("/api/v1/discover/items", headers=extra).json()["items"]
        return {(item.get("post") or item.get("listing") or item)["content_id"] for item in items}

    def foryou_ids(extra: dict[str, str]) -> set[str]:
        return {item["content_id"] for item in client.get("/api/v1/me/feed?tab=foryou", headers=extra).json()["items"]}

    assert content_id not in discover_ids({})  # 没选国家：只看国际
    assert content_id in discover_ids({"X-Region": "UK"})
    assert content_id in foryou_ids({"X-Region": "uk"})
    assert content_id not in discover_ids({"X-Region": "ZZ"})  # 没开通的国家不算


def test_home_rail_ranks_by_heat_in_visible_regions(client):
    """右栏「今日 / 本周」：浏览 + 点赞×3 + 收藏×5 排序；挂两个频道只出一次；别国、超过一周的不出现。"""
    from app.models import ContentReaction, User

    session = client.session_factory()
    now = datetime.now(timezone.utc)
    life = global_channel(session, "rail-life", "生活")
    life2 = global_channel(session, "rail-life2", "生活")
    uk = Channel(code="rail-uk", name_hans="英国", name_hant="英國", kind="official_curated", region_code="UK", is_active=True)
    session.add(uk)
    fans = [User(email=f"fan{i}@example.com", password_hash="x", display_name=f"粉{i}") for i in range(3)]
    session.add_all(fans)
    session.flush()

    def post(title: str, days_ago: float, views: int, *channels: str) -> str:
        content = Content(type="post", status="published", title=title, summary="摘要", view_count=views,
                          published_at=now - timedelta(days=days_ago))
        session.add(content)
        session.flush()
        for channel_id in channels:
            session.add(ChannelItem(channel_id=channel_id, content_id=content.id, added_at=content.published_at))
        return content.id

    viewed = post("浏览多", 0.1, 6, life)            # 6 分
    favourite = post("收藏多", 0.2, 0, life, life2)  # 两个收藏 = 10 分，挂了两个频道
    liked = post("点赞多", 0.3, 0, life)             # 一个赞 = 3 分
    post("英国本地", 0.1, 50, uk.id)                 # 游客没选国家看不到
    post("上个月的", 30, 99, life)                   # 超过一周
    session.add_all([
        ContentReaction(user_id=fans[0].id, content_id=favourite, favorited=True),
        ContentReaction(user_id=fans[1].id, content_id=favourite, favorited=True),
        ContentReaction(user_id=fans[2].id, content_id=liked, liked=True),
    ])
    session.commit()
    session.close()

    rail = client.get("/api/v1/discover/home-rail").json()
    week_ids = [card["content_id"] for card in rail["week"]]
    assert week_ids == [favourite, viewed, liked]
    assert [card["content_id"] for card in rail["today"]] == [favourite, viewed, liked]
    uk_rail = client.get("/api/v1/discover/home-rail", headers={"X-Region": "UK"}).json()
    assert uk_rail["week"][0]["title"] == "英国本地"

from datetime import datetime, timezone

from app.models import Channel, ChannelItem, Content

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str, name: str = "用户") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": name, "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def approve(client, token: str, content_id: str) -> None:
    response = client.post(
        f"/api/v1/moderation/{content_id}/decision",
        headers=headers(token),
        json={"decision": "approve"},
    )
    assert response.status_code == 200, response.text


def approve(client, token: str, content_id: str) -> None:
    response = client.post(
        f"/api/v1/moderation/{content_id}/decision",
        headers=headers(token),
        json={"decision": "approve"},
    )
    assert response.status_code == 200, response.text


def verify(client, token: str, phone: str) -> None:
    response = client.post(
        "/api/v1/auth/verify-phone",
        headers=headers(token),
        json={"phone": phone, "code": "246810"},
    )
    assert response.status_code == 200, response.text


def housing_channel(client) -> str:
    session = client.session_factory()
    channel = Channel(
        code="uk-housing-list",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        category="房产",
        region_code="UK",
        is_active=True,
    )
    session.add(channel)
    session.commit()
    channel_id = channel.id
    session.close()
    return channel_id


def test_profile_report_can_suspend_user(client):
    reporter = register(client, "reporter@example.com", "举报人")
    register(client, "reported@example.com", "被举报")
    session = client.session_factory()
    from sqlalchemy import select

    from app.models import User

    reported_id = session.scalar(select(User.id).where(User.email == "reported@example.com"))
    session.close()
    filed = client.post(
        f"/api/v1/users/{reported_id}/report",
        headers=headers(reporter),
        json={"reason": "scam"},
    )
    assert filed.status_code == 200, filed.text
    again = client.post(
        f"/api/v1/users/{reported_id}/report",
        headers=headers(reporter),
        json={"reason": "scam"},
    )
    assert again.status_code == 409
    decided = client.post(
        f"/api/v1/moderation/cases/{filed.json()['case_id']}/decision",
        headers=headers(reporter),
        json={"decision": "remove"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "suspended"
    assert client.get(f"/api/v1/users/{reported_id}").status_code == 404


def test_settings_script_and_block_list(client):
    owner = register(client, "settings@example.com", "主人")
    register(client, "blocked-person@example.com", "路人")
    session = client.session_factory()
    from sqlalchemy import select

    from app.models import User

    other_id = session.scalar(select(User.id).where(User.email == "blocked-person@example.com"))
    session.close()
    assert client.get("/api/v1/me/script", headers=headers(owner)).json()["script_pref"] == "hans"
    updated = client.put("/api/v1/me/script", headers=headers(owner), json={"script_pref": "hant"})
    assert updated.json()["script_pref"] == "hant"
    assert client.put(f"/api/v1/me/blocks/{other_id}", headers=headers(owner)).status_code == 200
    listed = client.get("/api/v1/me/blocks", headers=headers(owner)).json()["items"]
    assert listed == [{"user_id": other_id, "display_name": "路人"}]
    assert client.delete(f"/api/v1/me/blocks/{other_id}", headers=headers(owner)).status_code == 200
    assert client.get("/api/v1/me/blocks", headers=headers(owner)).json()["items"] == []


def test_repost_keeps_source_and_skips_for_you(client):
    author = register(client, "origin@example.com", "作者")
    verify(client, author, "+447700900931")
    forwarder = register(client, "forward@example.com", "转发者")
    verify(client, forwarder, "+447700900932")
    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(author),
        json={"channel_id": channel_id, "title": "周末聚会", "body": "欢迎来"},
    )
    content_id = created.json()["content_id"]
    approve(client, author, content_id)
    forwarded = client.post(
        f"/api/v1/contents/{content_id}/repost",
        headers=headers(forwarder),
        json={"channel_id": channel_id, "body": "也推荐看看"},
    )
    assert forwarded.status_code == 200, forwarded.text
    repost_id = forwarded.json()["content_id"]
    again = client.post(
        f"/api/v1/contents/{content_id}/repost",
        headers=headers(forwarder),
        json={"channel_id": channel_id},
    )
    assert again.json()["content_id"] == repost_id
    # 转发和发帖同一套规则：新用户的前几条要先审
    assert forwarded.json()["status"] == "pending"
    assert client.get(f"/api/v1/contents/{repost_id}").status_code == 404
    approve(client, author, repost_id)
    rows = client.get(f"/api/v1/channels/{channel_id}/items", headers=headers(forwarder)).json()["items"]
    original = next(item for item in rows if item["content_id"] == content_id)
    copy = next(item for item in rows if item["content_id"] == repost_id)
    assert original["reposted"] is True
    assert copy["repost_of"]["content_id"] == content_id
    assert copy["repost_of"]["title"] == "周末聚会"
    assert copy["licence_ref"] == original["licence_ref"]
    detail = client.get(f"/api/v1/contents/{repost_id}", headers=headers(forwarder)).json()
    assert detail["repost_of"]["title"] == "周末聚会"
    assert detail["channel_id"] == channel_id
    assert detail["source_name"] == original["source_name"]
    foryou = client.get("/api/v1/me/feed?tab=foryou", headers=headers(forwarder))
    assert all(item["content_id"] != repost_id for item in foryou.json()["items"])
    # 原帖删掉后，转发里抄下来的标题和摘要也不再露出
    assert client.delete(f"/api/v1/contents/{content_id}", headers=headers(author)).status_code == 200
    assert client.get(f"/api/v1/contents/{repost_id}", headers=headers(forwarder)).status_code == 404
    rows = client.get(f"/api/v1/channels/{channel_id}/items", headers=headers(forwarder)).json()["items"]
    assert all(item["content_id"] != repost_id for item in rows)


def test_reply_stays_hidden_until_approved(client):
    author = register(client, "reply-author@example.com", "作者")
    verify(client, author, "+447700900921")
    reader = register(client, "reply-reader@example.com", "读者")
    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(author),
        json={"channel_id": channel_id, "title": "周末聚会", "body": "欢迎来"},
    )
    content_id = created.json()["content_id"]
    approve(client, author, content_id)
    replied = client.post(
        f"/api/v1/contents/{content_id}/comments",
        headers=headers(reader),
        json={"body": "我到"},
    )
    assert replied.status_code == 200, replied.text
    comment_id = replied.json()["comment_id"]
    assert replied.json()["status"] == "pending"
    hidden = client.get(f"/api/v1/contents/{content_id}/comments")
    assert hidden.json()["items"] == []
    mine = client.get(f"/api/v1/contents/{content_id}/comments", headers=headers(reader)).json()["items"]
    assert mine[0]["author_name"] == "读者"
    too_early = client.post(
        f"/api/v1/contents/{content_id}/comments/{comment_id}/like",
        headers=headers(reader),
    )
    assert too_early.status_code == 404
    assert client.post(
        f"/api/v1/moderation/comments/{comment_id}/decision",
        headers=headers(author),
        json={"decision": "approve"},
    ).status_code == 200
    shown = client.get(f"/api/v1/contents/{content_id}/comments").json()["items"]
    assert shown[0]["body"] == "我到"
    liked = client.post(
        f"/api/v1/contents/{content_id}/comments/{comment_id}/like",
        headers=headers(author),
    )
    assert liked.status_code == 200, liked.text
    assert liked.json() == {"liked": True, "like_count": 1}
    listed = client.get(f"/api/v1/contents/{content_id}/comments", headers=headers(author)).json()["items"][0]
    assert listed["liked"] is True
    assert listed["like_count"] == 1
    notes = client.get("/api/v1/me/notifications", headers=headers(author)).json()["items"]
    assert notes[0]["kind"] == "reply"


def test_publish_keywords_are_capped_and_searchable(client):
    owner = register(client, "tags@example.com", "作者")
    verify(client, owner, "+447700900801")
    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={
            "channel_id": channel_id,
            "title": "周末看房",
            "body": "周六下午 #伦敦",
            "keywords": ["租房", "合租", "签证", "兼职", "二手", "家具"],
            "city_topic": "伦敦",
            "keyword_source": "ai_auto",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["keywords"] == ["租房", "合租", "签证", "兼职", "二手"]
    assert created.json()["keyword_source"] == "ai_auto"
    assert created.json()["city_topic"] == "伦敦"
    content_id = created.json()["content_id"]
    detail = client.get(f"/api/v1/contents/{content_id}", headers=headers(owner))
    assert detail.json()["keywords"] == ["租房", "合租", "签证", "兼职", "二手"]
    assert detail.json()["city_topic"] == "伦敦"
    assert detail.json()["keyword_source"] == "ai_auto"
    assert detail.json()["author_handle"] == "tags"
    assert "伦敦" not in detail.json()["keywords"]
    # 详情页直接展示多图与发布时间
    assert detail.json()["image_keys"] == []
    assert "published_at" in detail.json()
    approve(client, owner, content_id)
    assert client.post(f"/api/v1/contents/{content_id}/like", headers=headers(owner)).json()["liked"] is True
    assert client.post(f"/api/v1/contents/{content_id}/favorite", headers=headers(owner)).json()["favorited"] is True
    mine = next(item for item in client.get(f"/api/v1/channels/{channel_id}/items", headers=headers(owner)).json()["items"] if item["content_id"] == content_id)
    guest = next(item for item in client.get(f"/api/v1/channels/{channel_id}/items").json()["items"] if item["content_id"] == content_id)
    assert mine["liked"] is True
    assert mine["author_handle"] == "tags"
    assert mine["favorited"] is True
    assert guest["liked"] is False
    found = client.get("/api/v1/search?q=租房")
    hit = next(item for item in found.json()["contents"] if item["content_id"] == content_id)
    assert hit["source_name"] == "作者"
    assert hit["author_handle"] == "tags"
    assert hit["channel_id"] == channel_id
    assert hit["type"] == "post"
    missed = client.get("/api/v1/search?q=家具")
    assert all(item["content_id"] != content_id for item in missed.json()["contents"])
    # % 和 _ 按字面匹配，不再当通配符命中全部内容
    assert client.get("/api/v1/search", params={"q": "%"}).json()["contents"] == []
    assert client.get("/api/v1/search", params={"q": "_"}).json()["contents"] == []
    hashed = client.get("/api/v1/search", params={"q": "#租房"}).json()
    assert content_id in [item["content_id"] for item in hashed["contents"]]
    assert hashed["users"] == []
    people = client.get("/api/v1/search", params={"q": "@Tags"}).json()
    assert people["users"][0]["handle"] == "tags"
    assert people["users"][0]["display_name"] == "作者"
    assert content_id in [item["content_id"] for item in people["contents"]]
    # 普通词也能按昵称搜到用户；内容结果带卡片字段和当前用户的点赞状态
    plain = client.get("/api/v1/search", params={"q": "作者"}).json()
    assert "tags" in [item["handle"] for item in plain["users"]]
    assert isinstance(hit["keywords"], list) and isinstance(hit["image_keys"], list)
    assert hit["published_at"] and hit["liked"] is False
    mine_hit = next(item for item in client.get("/api/v1/search", params={"q": "租房"}, headers=headers(owner)).json()["contents"] if item["content_id"] == content_id)
    assert mine_hit["liked"] is True and mine_hit["favorited"] is True
    auto = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "找房", "body": "想在伦敦租房，整租一居"},
    )
    assert auto.status_code == 200, auto.text
    assert auto.json()["keywords"] == ["租房"]
    assert auto.json()["keyword_source"] == "ai_auto"
    filled = client.get(f"/api/v1/contents/{auto.json()['content_id']}", headers=headers(owner)).json()
    assert filled["keywords"] == ["租房"]
    assert filled["keyword_source"] == "ai_auto"
    listed = client.post(
        "/api/v1/listings",
        headers=headers(owner),
        json={
            "channel_id": channel_id,
            "title": "一居出租",
            "body": "伦敦整租一居，可看房",
            "category": "房产",
            "kind": "rent",
            "area": "伦敦",
            "price_amount": "1500",
            "price_unit": "月",
            "contact": "sms: 1",
            "attrs": {},
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["type"] == "listing"
    assert listed.json()["keyword_source"] == "ai_auto"
    assert listed.json()["keywords"][:2] == ["房产", "租房"]
    listing_card = client.get(f"/api/v1/contents/{listed.json()['content_id']}", headers=headers(owner)).json()
    assert listing_card["keyword_source"] == "ai_auto"
    assert listing_card["keywords"][:2] == ["房产", "租房"]


def test_video_post_needs_rights_and_topic_needs_a_tag(client):
    owner = register(client, "video-owner@example.com", "拍客")
    verify(client, owner, "+447700900841")
    channel_id = housing_channel(client)
    signed = client.post(
        "/api/v1/uploads/sign",
        headers=headers(owner),
        json={"content_type": "video/mp4"},
    )
    assert signed.status_code == 200, signed.text
    key = signed.json()["object_key"]
    stored = client.put(f"/api/v1/uploads/{key}", headers=headers(owner), content=b"\x00\x00\x00\x18ftyp")
    assert stored.status_code == 200, stored.text
    missing = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={
            "channel_id": channel_id,
            "title": "一段视频",
            "body": "自己拍的街道",
            "post_type": "video",
            "video_key": key,
        },
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == "RIGHTS_REQUIRED"
    posted = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={
            "channel_id": channel_id,
            "title": "一段视频",
            "body": "自己拍的街道",
            "post_type": "video",
            "video_key": key,
            "rights_confirmed": True,
        },
    )
    assert posted.status_code == 200, posted.text
    detail = client.get(f"/api/v1/contents/{posted.json()['content_id']}", headers=headers(owner)).json()
    assert detail["type"] == "video"
    assert detail["video_key"] == key
    assert detail["rights_confirmed"] is True
    bare = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "话题", "body": "没有标签的正文", "post_type": "topic"},
    )
    assert bare.status_code == 400
    assert bare.json()["code"] == "TOPIC_REQUIRED"
    tagged = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "话题", "body": "周末 #伦敦", "post_type": "topic"},
    )
    assert tagged.status_code == 200, tagged.text


def test_roaming_can_read_uk_but_not_post(client):
    owner = register(client, "roam-owner@example.com", "房东")
    verify(client, owner, "+447700900831")
    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "英国帖", "body": "给漫游的人看"},
    )
    content_id = created.json()["content_id"]
    approve(client, owner, content_id)
    visitor = register(client, "roam-visitor@example.com", "旅客")
    verify(client, visitor, "+447700900832")
    switched = client.post(
        "/api/v1/me/regions",
        headers=headers(visitor),
        json={"region_code": "JP", "source": "manual", "browse_region_code": "UK"},
    )
    assert switched.status_code == 200, switched.text
    assert switched.json()["roaming"] is True
    assert switched.json()["station_name"] == "英国"
    assert switched.json()["station_city"] == "伦敦"
    detail = client.get(f"/api/v1/channels/{channel_id}", headers=headers(visitor)).json()
    assert detail["region_blocked"] is False
    assert client.get(f"/api/v1/channels/{channel_id}/items", headers=headers(visitor)).json()["items"]
    blocked = client.post(
        "/api/v1/contents",
        headers=headers(visitor),
        json={"channel_id": channel_id, "title": "想发", "body": "漫游时不该发出去"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "ROAMING_READONLY"


def test_library_counts_saves_and_follows_apart(client):
    owner = register(client, "library@example.com", "收藏者")
    verify(client, owner, "+447700900821")
    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "想留着", "body": "这条要收藏"},
    )
    content_id = created.json()["content_id"]
    approve(client, owner, content_id)
    liked = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "只是喜欢", "body": "不放进收藏"},
    )
    liked_id = liked.json()["content_id"]
    approve(client, owner, liked_id)
    client.post(f"/api/v1/contents/{content_id}/favorite", headers=headers(owner))
    client.post(f"/api/v1/contents/{liked_id}/like", headers=headers(owner))
    client.put(f"/api/v1/me/subscriptions/{channel_id}", headers=headers(owner))
    library = client.get("/api/v1/me/favorites", headers=headers(owner)).json()
    assert library["saved_count"] == 1
    assert library["followed_count"] == 1
    assert library["paused_count"] == 0
    assert [item["content_id"] for item in library["items"]] == [content_id]


def test_other_country_keeps_follows_saves_and_rooms(client):
    token = register(client, "pause@example.com", "切换")
    verify(client, token, "+447700900841")
    session = client.session_factory()
    uk = Channel(
        code="uk-pause",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    world = Channel(
        code="world-share",
        name_hans="国际分享",
        name_hant="國際分享",
        kind="official_curated",
        region_code="GLOBAL",
        is_active=True,
    )
    session.add_all([uk, world])
    session.commit()
    uk_id, world_id = uk.id, world.id
    session.close()
    created = client.post(
        "/api/v1/contents",
        headers=headers(token),
        json={"channel_id": uk_id, "title": "英国房源", "body": "切走后先藏起来"},
    )
    content_id = created.json()["content_id"]
    approve(client, token, content_id)
    client.post(f"/api/v1/contents/{content_id}/favorite", headers=headers(token))
    client.put(f"/api/v1/me/subscriptions/{uk_id}", headers=headers(token))
    client.put(f"/api/v1/me/subscriptions/{world_id}", headers=headers(token))
    room = client.post(
        "/api/v1/channels",
        headers=headers(token),
        json={"name": "英国追更房间", "parent_channel_id": uk_id},
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["channel_id"]
    client.post("/api/v1/me/regions", headers=headers(token), json={"region_code": "GLOBAL", "source": "manual"})
    feed = client.get("/api/v1/me/feed", headers=headers(token)).json()
    assert feed["joined_count"] == 1
    assert feed["paused_count"] == 1
    assert content_id not in [item["content_id"] for item in feed["items"]]
    follows = client.get("/api/v1/me/subscriptions", headers=headers(token)).json()
    assert [item["channel_id"] for item in follows["items"]] == [world_id]
    assert follows["paused_count"] == 1
    library = client.get("/api/v1/me/favorites", headers=headers(token)).json()
    assert library["saved_count"] == 0
    assert library["followed_count"] == 1
    assert library["paused_count"] == 2
    rooms = client.get("/api/v1/me/channels", headers=headers(token)).json()
    assert rooms["items"] == []
    assert rooms["paused_count"] == 1
    client.post("/api/v1/me/regions", headers=headers(token), json={"region_code": "UK", "source": "manual"})
    restored = client.get("/api/v1/me/feed", headers=headers(token)).json()
    assert restored["joined_count"] == 2
    assert restored["paused_count"] == 0
    assert content_id in [item["content_id"] for item in restored["items"]]
    assert client.get("/api/v1/me/favorites", headers=headers(token)).json()["saved_count"] == 1
    mine = client.get("/api/v1/me/channels", headers=headers(token)).json()
    assert [item["channel_id"] for item in mine["items"]] == [room_id]
    assert mine["items"][0]["parent_name_hans"] == "英国租房"
    assert mine["items"][0]["entry_count"] == 0
    assert mine["paused_count"] == 0


def test_profile_post_skips_category_and_room_uses_parent(client):
    owner = register(client, "profile-post@example.com", "近况")
    verify(client, owner, "+447700900811")
    channel_id = housing_channel(client)
    assert client.get(f"/api/v1/channels/{channel_id}").json()["category"] == "房产"
    posted = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"title": "今天", "body": "随便写一点近况"},
    )
    assert posted.status_code == 200, posted.text
    content_id = posted.json()["content_id"]
    detail = client.get(f"/api/v1/contents/{content_id}", headers=headers(owner)).json()
    assert detail["channel_id"] is None
    assert detail["category"] is None
    approve(client, owner, content_id)
    posts = client.get(f"/api/v1/users/{detail['author_id']}/posts").json()["items"]
    assert posts[0]["content_id"] == content_id
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "看房笔记", "parent_channel_id": channel_id},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}").json()["category"] == "房产"


def test_listing_contact_keywords_like_and_recommendation(client):
    owner = register(client, "landlord@example.com", "房东")
    verify(client, owner, "+447700900301")
    guest = register(client, "guest@example.com", "访客")
    channel_id = housing_channel(client)
    client.post("/api/v1/me/regions", headers=headers(owner), json={"region_code": "UK", "source": "manual"})

    mismatch = client.post(
        "/api/v1/listings",
        headers=headers(owner),
        json={
            "channel_id": channel_id,
            "title": "出租单间",
            "body": "伦敦出租单间，近地铁。",
            "category": "招聘",
            "kind": "job",
            "area": "伦敦",
            "price_amount": "15",
            "price_unit": "小时",
            "contact": "wechat: landlord",
        },
    )
    assert mismatch.status_code == 400

    created = client.post(
        "/api/v1/listings",
        headers=headers(owner),
        json={
            "channel_id": channel_id,
            "title": "出租单间",
            "body": "伦敦出租单间，近地铁。",
            "category": "房产",
            "kind": "rent",
            "area": "伦敦 · Stratford",
            "price_amount": "900",
            "price_unit": "月",
            "contact": "wechat: landlord",
            "attrs": {"roomType": "单间", "unknown": "丢弃"},
        },
    )
    assert created.status_code == 200, created.text
    listing_id = created.json()["content_id"]
    assert created.json()["status"] == "pending"
    assert client.get(f"/api/v1/listings/{listing_id}", headers=headers(guest)).status_code == 404
    pending = client.get(f"/api/v1/listings/{listing_id}", headers=headers(owner))
    assert pending.json()["certified"] is False
    approve(client, owner, listing_id)
    assert client.get(f"/api/v1/channels/{channel_id}").json()["certified"] is True
    published = client.get(f"/api/v1/listings/{listing_id}", headers=headers(owner)).json()
    assert published["certified"] is True
    assert published["author_name"] == "房东"
    assert published["author_handle"] == "landlord"
    stream = client.get(f"/api/v1/channels/{channel_id}/items")
    listing_card = next(item for item in stream.json()["items"] if item["content_id"] == listing_id)
    assert listing_card["type"] == "listing"
    assert listing_card["listing"]["price_amount"] == "900"
    assert listing_card["listing"]["certified"] is True
    assert listing_card["listing"]["expired"] is False
    assert listing_card["listing"]["expires_at"]
    assert listing_card["listing"]["currency"] == "GBP"

    hidden = client.get(f"/api/v1/listings/{listing_id}", headers=headers(guest))
    assert hidden.json()["placeholder"] is True

    client.post("/api/v1/me/regions", headers=headers(guest), json={"region_code": "GLOBAL", "source": "manual", "browse_region_code": "UK"})
    visible = client.get(f"/api/v1/listings/{listing_id}", headers=headers(guest))
    assert visible.json()["placeholder"] is False
    assert visible.json()["currency"] == "GBP"
    assert visible.json()["contact_views_remaining"] == 5
    assert visible.json()["contact_views_limit"] == 5
    assert "unknown" not in visible.json()["attrs"]

    contact = client.post(f"/api/v1/listings/{listing_id}/contact", headers=headers(guest))
    assert contact.status_code == 200
    assert contact.json()["contact"] == "wechat: landlord"
    assert contact.json()["contact_views_remaining"] == 4
    for _ in range(4):
        assert client.post(f"/api/v1/listings/{listing_id}/contact", headers=headers(guest)).status_code == 200
    blocked_contact = client.post(f"/api/v1/listings/{listing_id}/contact", headers=headers(guest))
    assert blocked_contact.status_code == 429
    assert blocked_contact.json()["code"] == "CONTACT_LIMIT"
    assert "私信咨询" in blocked_contact.json()["message"]

    words = client.post(
        "/api/v1/ai/keywords",
        headers=headers(owner),
        json={"title": "出租单间", "body": "伦敦出租，租金面议", "category": "房产"},
    )
    assert words.status_code == 200
    assert words.json()["keywords"][0] == "房产"
    assert "租房" in words.json()["keywords"]
    assert len(words.json()["keywords"]) <= 5

    liked = client.post(f"/api/v1/contents/{listing_id}/like", headers=headers(guest))
    assert liked.json()["liked"] is True

    foryou = client.get("/api/v1/me/feed?tab=foryou", headers=headers(guest))
    assert all(item["content_id"] != listing_id for item in foryou.json()["items"])

    discover = client.get("/api/v1/discover/listings", headers=headers(guest))
    found = next(item for item in discover.json()["items"] if item["content_id"] == listing_id)
    assert found["source_name"]
    assert found["currency"] == "GBP"
    assert found["author_handle"] == "landlord"
    assert found["author_id"] == published["author_id"]
    assert "licence_ref" in found

    session = client.session_factory()
    stored = session.get(Content, listing_id)
    stored.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    session.commit()
    session.close()
    expired_card = next(
        item
        for item in client.get(f"/api/v1/channels/{channel_id}/items").json()["items"]
        if item["content_id"] == listing_id
    )
    assert expired_card["listing"]["expired"] is True

    closed = client.post(f"/api/v1/listings/{listing_id}/close", headers=headers(owner), json={"reason": "rented"})
    assert closed.status_code == 200
    gone = client.get("/api/v1/discover/listings", headers=headers(guest))
    assert all(item["content_id"] != listing_id for item in gone.json()["items"])


def test_direct_message_request_and_listing_bypass(client):
    host = register(client, "host@example.com", "房东")
    stranger = register(client, "stranger@example.com", "路人")
    verify(client, host, "+447700900302")
    channel_id = housing_channel(client)
    listing = client.post(
        "/api/v1/listings",
        headers=headers(host),
        json={
            "channel_id": channel_id,
            "title": "二手书桌",
            "body": "九成新书桌转让",
            "category": "市场",
            "kind": "secondhand",
            "area": "伦敦",
            "price_amount": "40",
            "price_unit": "月",
            "contact": "sms: 1",
        },
    )
    assert listing.status_code == 400

    market = client.session_factory()
    row = Channel(
        code="uk-market",
        name_hans="二手",
        name_hant="二手",
        kind="official_auto",
        category="市场",
        region_code="UK",
        is_active=True,
    )
    market.add(row)
    market.commit()
    market_id = row.id
    market.close()
    listing = client.post(
        "/api/v1/listings",
        headers=headers(host),
        json={
            "channel_id": market_id,
            "title": "二手书桌",
            "body": "九成新书桌转让",
            "category": "市场",
            "kind": "secondhand",
            "area": "伦敦",
            "price_amount": "40",
            "price_unit": "",
            "contact": "sms: 1",
            "attrs": {"condition": "九成新"},
        },
    )
    assert listing.status_code == 200, listing.text
    listing_id = listing.json()["content_id"]
    approve(client, host, listing_id)

    session = client.session_factory()
    from sqlalchemy import select
    from app.models import User

    host_id = session.scalar(select(User.id).where(User.email == "host@example.com"))
    session.close()

    requested = client.post(
        "/api/v1/me/messages",
        headers=headers(stranger),
        json={"to_user_id": host_id, "body": "你好"},
    )
    assert requested.status_code == 200
    assert requested.json()["status"] == "request"
    assert client.get("/api/v1/me/messages", headers=headers(host)).json()["request_count"] == 1

    inquiry = client.post(
        "/api/v1/me/messages",
        headers=headers(stranger),
        json={"to_user_id": host_id, "body": "还在吗", "listing_id": listing_id},
    )
    assert inquiry.status_code == 200, inquiry.text
    assert inquiry.json()["status"] == "active"
    assert inquiry.json()["listing_ref"]["title"] == "二手书桌"
    assert inquiry.json()["listing_ref"]["area"] == "伦敦"
    assert inquiry.json()["listing_ref"]["price"] == "40"
    assert inquiry.json()["listing_ref"]["currency"] == "GBP"
    assert inquiry.json()["suggested_text"] == "你好，想了解一下这套房源是否还在？"
    thread_id = inquiry.json()["thread_id"]
    inbox = client.get("/api/v1/me/messages", headers=headers(host))
    row = next(item for item in inbox.json()["items"] if item["thread_id"] == thread_id)
    assert row["peer_name"] == "路人"
    assert row["preview"] == "还在吗"
    assert row["listing_ref"]["area"] == "伦敦"
    assert row["listing_ref"]["currency"] == "GBP"
    assert row["unread"] == 2
    notes = client.get("/api/v1/me/notifications", headers=headers(host))
    assert notes.json()["items"][0]["unread"] is True
    cleared = client.post("/api/v1/me/notifications/read", headers=headers(host))
    assert cleared.json()["marked"] == 1
    marked = client.post(f"/api/v1/me/messages/{thread_id}/read", headers=headers(host))
    assert marked.status_code == 200
    assert marked.json()["marked"] == 2


def test_room_update_notifies_subscribers_except_muted(client):
    owner = register(client, "room-note@example.com", "房主")
    verify(client, owner, "+447700900911")
    member = register(client, "room-member@example.com", "成员")
    quiet = register(client, "room-quiet@example.com", "静音")
    session = client.session_factory()
    parent = Channel(
        code="uk-notes",
        name_hans="生活",
        name_hant="生活",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(parent)
    session.commit()
    parent_id = parent.id
    session.close()
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "看房笔记", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    assert client.put(f"/api/v1/me/subscriptions/{room_id}", headers=headers(member)).status_code == 200
    member_list = client.get("/api/v1/me/channels", headers=headers(member)).json()
    joined = next(item for item in member_list["items"] if item["channel_id"] == room_id)
    assert joined["role"] == "member"
    assert joined["parent_name_hans"] == "生活"
    assert joined["room_type"] == "general"
    assert joined["room_type_label"] == "通用"
    assert joined["entry_count"] == 0
    assert member_list["owned_count"] == 0
    assert member_list["room_limit"] == 20
    owner_list = client.get("/api/v1/me/channels", headers=headers(owner)).json()
    owned = next(item for item in owner_list["items"] if item["channel_id"] == room_id)
    assert owned["role"] == "owner"
    assert owner_list["owned_count"] == 1
    assert client.put(f"/api/v1/me/subscriptions/{room_id}", headers=headers(quiet)).status_code == 200
    assert client.patch(
        f"/api/v1/me/subscriptions/{room_id}",
        headers=headers(quiet),
        json={"is_muted": True},
    ).status_code == 200
    announced = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "周日看房", "body": "下午两点"},
    )
    assert announced.status_code == 200, announced.text
    notes = client.get("/api/v1/me/notifications", headers=headers(member)).json()["items"]
    assert notes[0]["kind"] == "room.update"
    assert announced.json()["content_id"] == notes[0]["content_id"]
    assert client.get("/api/v1/me/notifications", headers=headers(quiet)).json()["items"] == []
    assert client.get("/api/v1/me/notifications", headers=headers(owner)).json()["items"] == []


def test_public_profile_lists_published_posts(client):
    author = register(client, "profile@example.com", "作者")
    verify(client, author, "+447700900901")
    reader = register(client, "reader@example.com", "读者")
    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(author),
        json={"channel_id": channel_id, "title": "周末聚会", "body": "欢迎来"},
    )
    content_id = created.json()["content_id"]
    session = client.session_factory()
    from sqlalchemy import select
    from app.models import User

    author_id = session.scalar(select(User.id).where(User.email == "profile@example.com"))
    session.close()
    hidden = client.get(f"/api/v1/users/{author_id}/posts")
    assert hidden.json()["items"] == []
    approve(client, author, content_id)
    shown = client.get(f"/api/v1/users/{author_id}/posts")
    post = shown.json()["items"][0]
    assert post["content_id"] == content_id
    assert post["channel_id"] == channel_id and post["liked"] is False  # 主页帖子是完整卡片，能直接点赞/转发
    card = client.get(f"/api/v1/channels/{channel_id}/items").json()["items"][0]
    assert card["author_name"] == "作者"
    assert card["author_id"] == author_id  # 卡片头像 / @handle 靠它进主页
    guest = client.get(f"/api/v1/users/{author_id}")
    assert guest.json()["following"] is False
    assert guest.json()["post_count"] == 1 and guest.json()["follower_count"] == 0
    followed = client.put(f"/api/v1/me/follows/{author_id}", headers=headers(reader))
    assert followed.status_code == 200
    seen = client.get(f"/api/v1/users/{author_id}", headers=headers(reader))
    assert seen.json()["display_name"] == "作者"
    assert seen.json()["following"] is True
    assert seen.json()["follower_count"] == 1 and seen.json()["joined_at"]


def test_recipient_can_delete_message_request(client):
    host = register(client, "inbox@example.com", "房东")
    stranger = register(client, "asker@example.com", "路人")
    session = client.session_factory()
    from sqlalchemy import select
    from app.models import User

    host_id = session.scalar(select(User.id).where(User.email == "inbox@example.com"))
    session.close()
    opened = client.post(
        "/api/v1/me/messages",
        headers=headers(stranger),
        json={"to_user_id": host_id, "body": "你好"},
    )
    thread_id = opened.json()["thread_id"]
    removed = client.delete(f"/api/v1/me/messages/{thread_id}", headers=headers(host))
    assert removed.status_code == 200
    assert client.get("/api/v1/me/messages", headers=headers(host)).json()["items"] == []
    sender_delete = client.delete(f"/api/v1/me/messages/{thread_id}", headers=headers(stranger))
    assert sender_delete.status_code == 404


def test_private_room_join_and_comment(client):
    owner = register(client, "room-owner@example.com", "房主")
    verify(client, owner, "+447700900401")
    guest = register(client, "room-guest@example.com", "访客")
    session = client.session_factory()
    parent = Channel(
        code="uk-life",
        name_hans="生活",
        name_hant="生活",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(parent)
    session.commit()
    parent_id = parent.id
    session.close()

    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "看房小组", "parent_channel_id": parent_id, "is_private": True},
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["channel_id"]
    approved = client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(guest)).status_code == 404
    announced = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "内部通知", "body": "只给成员看"},
    )
    assert announced.status_code == 200
    directory = client.get("/api/v1/channels?kind=room").json()["items"]
    assert room_id not in {item["id"] for item in directory}

    blocked = client.post(
        f"/api/v1/channels/{room_id}/comments",
        headers=headers(guest),
        json={"body": "还没加入"},
    )
    assert blocked.status_code == 403

    requested = client.post(f"/api/v1/channels/{room_id}/join-requests", headers=headers(guest))
    assert requested.status_code == 200, requested.text
    request_id = requested.json()["request_id"]
    approved_join = client.post(
        f"/api/v1/channels/{room_id}/join-requests/{request_id}/approve",
        headers=headers(owner),
    )
    assert approved_join.status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(guest)).status_code == 200

    comment = client.post(
        f"/api/v1/channels/{room_id}/comments",
        headers=headers(guest),
        json={"body": "@房主 周日看房 #伦敦"},
    )
    assert comment.status_code == 200, comment.text
    assert comment.json()["status"] == "pending"
    assert client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(owner)).json()["items"] == []
    listed = client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(guest))
    item = listed.json()["items"][0]
    assert item["status"] == "pending"
    decided = client.post(
        f"/api/v1/moderation/comments/{comment.json()['comment_id']}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert decided.status_code == 200
    listed = client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(owner))
    item = listed.json()["items"][0]
    assert item["mention_count"] == 1
    assert item["keyword_count"] == 1

    removed = client.delete(
        f"/api/v1/channels/{room_id}/comments/{comment.json()['comment_id']}",
        headers=headers(guest),
    )
    assert removed.status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(guest)).json()["items"] == []


def test_image_detail_discover_and_contract(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.api.v1.uploads.upload_root", lambda: tmp_path)
    owner = register(client, "poster@example.com", "作者")
    verify(client, owner, "+447700900501")
    signed = client.post(
        "/api/v1/uploads/sign",
        headers=headers(owner),
        json={"content_type": "image/png"},
    )
    assert signed.status_code == 200, signed.text
    key = signed.json()["object_key"]
    stored = client.put(f"/api/v1/uploads/{key}", headers=headers(owner), content=b"\x89PNG")
    assert stored.status_code == 200

    channel_id = housing_channel(client)
    created = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": channel_id, "title": "带图动态", "body": "看这张图", "image_key": key},
    )
    assert created.status_code == 200, created.text
    detail = client.get(f"/api/v1/contents/{created.json()['content_id']}", headers=headers(owner))
    assert detail.status_code == 200
    assert detail.json()["image_key"] == key
    assert detail.json()["source_name"] == "作者"
    hidden = client.get(f"/api/v1/contents/{created.json()['content_id']}")
    assert hidden.status_code == 404

    now = datetime.now(timezone.utc)
    session = client.session_factory()
    news = Content(
        type="news",
        status="published",
        title="发现页要闻",
        summary="公开来源",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/news",
        published_at=now,
    )
    session.add(news)
    session.flush()
    session.add(ChannelItem(channel_id=channel_id, content_id=news.id, added_at=now))
    session.commit()
    session.close()

    client.post(
        "/api/v1/me/regions",
        headers=headers(owner),
        json={"region_code": "UK", "source": "manual"},
    )
    discovered = client.get("/api/v1/discover/items", headers=headers(owner))
    titles = [item["title"] for item in discovered.json()["items"]]
    assert discovered.json()["updated_count"] >= 1
    assert "房产" in discovered.json()["categories"]
    assert "发现页要闻" in titles
    assert "带图动态" not in titles
    card = next(item for item in discovered.json()["items"] if item["title"] == "发现页要闻")
    assert card["licence_ref"] == "OGL v3.0"
    # 发现页卡片带当前用户的互动状态：点赞后再取，liked 为真；游客一律为假。
    assert (card["liked"], card["favorited"], card["reposted"]) == (False, False, False)
    client.post(f"/api/v1/contents/{card['content_id']}/like", headers=headers(owner))
    after_like = client.get("/api/v1/discover/items", headers=headers(owner)).json()["items"]
    assert next(i for i in after_like if i["content_id"] == card["content_id"])["liked"] is True
    guest_cards = client.get("/api/v1/discover/items").json()["items"]
    assert all(i["liked"] is False for i in guest_cards)
    # 地区筛选：回传当前国家；只能在可见范围内收窄，不会放宽（游客选 UK 也看不到 UK 频道）。
    assert discovered.json()["region"] == {"code": "UK", "name": "英国"}
    uk_only = client.get("/api/v1/discover/items?region=UK", headers=headers(owner)).json()["items"]
    assert uk_only and "发现页要闻" in [i["title"] for i in uk_only]
    global_only = client.get("/api/v1/discover/items?region=GLOBAL", headers=headers(owner)).json()["items"]
    assert "发现页要闻" not in [i["title"] for i in global_only]
    guest_uk = client.get("/api/v1/discover/items?region=UK").json()
    assert guest_uk["region"]["code"] == "GLOBAL" and guest_uk["items"] == []
    session = client.session_factory()
    for index in range(4):
        session.add(
            Channel(
                code=f"uk-extra-{index}",
                name_hans=f"补充频道{index}",
                name_hant=f"補充頻道{index}",
                kind="official_curated",
                region_code="UK",
                category="生活",
                is_active=True,
            )
        )
    session.commit()
    session.close()
    recommended = client.get("/api/v1/channels/recommended", headers=headers(owner)).json()["items"]
    assert len(recommended) == 3
    assert all(item["region_code"] in {"UK", "GLOBAL"} for item in recommended)
    guest_recommended = client.get("/api/v1/channels/recommended").json()["items"]
    assert all(item["region_code"] == "GLOBAL" for item in guest_recommended)

    badges = client.get("/api/v1/me/badges", headers=headers(owner))
    assert badges.status_code == 200
    assert badges.json()["total"] == 0

    paths = client.app.openapi()["paths"]
    for path in (
        "/api/v1/me/feed",
        "/api/v1/me/regions",
        "/api/v1/me/messages",
        "/api/v1/me/badges",
        "/api/v1/channels/recommended",
        "/api/v1/listings",
        "/api/v1/discover/listings",
        "/api/v1/discover/items",
        "/api/v1/uploads/sign",
        "/api/v1/contents/{content_id}",
    ):
        assert path in paths


def test_source_framing_headers_downgrade_embed(monkeypatch):
    from app.embed import framing_blocked, resolve_embed_url

    assert framing_blocked({"X-Frame-Options": "DENY"}) is True
    assert framing_blocked({"Content-Security-Policy": "frame-ancestors 'none'"}) is True
    assert framing_blocked({"X-Frame-Options": "ALLOWALL"}) is False
    monkeypatch.setattr(
        "app.embed.inspect_source",
        lambda _url: {"framing_blocked": True, "source_title": "源站标题"},
    )
    resolved = resolve_embed_url("https://www.youtube.com/watch?v=abcdefghijk")
    assert resolved["embed_status"] == "fallback"
    assert resolved["source_title"] == "源站标题"
    assert resolved["consent_required"] is False


def test_embed_recheck_removes_deleted_source(client, monkeypatch):
    owner = register(client, "recheck@example.com", "房主")
    verify(client, owner, "+447700900701")
    channel_id = housing_channel(client)
    created = client.post(
        f"/api/v1/channels/{channel_id}/items/embed",
        headers=headers(owner),
        json={"url": "https://www.youtube.com/watch?v=zzzzzzzzzzz", "title": "可能已删除"},
    )
    assert created.status_code == 200, created.text
    content_id = created.json()["content_id"]
    approve(client, owner, content_id)
    monkeypatch.setattr(
        "app.api.v1.embed.inspect_source",
        lambda _url: {"framing_blocked": False, "source_title": None, "status_code": 404},
    )
    checked = client.post("/api/v1/embed/recheck", headers=headers(owner))
    assert checked.status_code == 200
    assert checked.json()["changed"] == 1
    card = next(item for item in client.get(f"/api/v1/channels/{channel_id}/items").json()["items"] if item["content_id"] == content_id)
    assert card["embed_status"] == "removed"


def test_embed_resolve_consent_and_not_recommended(client):
    owner = register(client, "embed-owner@example.com", "房主")
    verify(client, owner, "+447700900601")
    channel_id = housing_channel(client)
    client.post("/api/v1/me/regions", headers=headers(owner), json={"region_code": "UK", "source": "manual"})

    short = client.post(
        "/api/v1/embed/resolve",
        headers=headers(owner),
        json={"url": "https://youtu.be/abcdefghijk"},
    )
    assert short.status_code == 400
    assert short.json()["code"] == "EMBED_SHORTLINK_REJECTED"

    youtube = client.post(
        "/api/v1/embed/resolve",
        headers=headers(owner),
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk&t=12"},
    )
    assert youtube.status_code == 200
    assert youtube.json()["embed_status"] == "embeddable"
    assert "embed_url" not in youtube.json()

    fallback = client.post(
        "/api/v1/embed/resolve",
        headers=headers(owner),
        json={"url": "https://www.bbc.co.uk/news/uk-1"},
    )
    assert fallback.json()["embed_status"] == "fallback"

    created = client.post(
        f"/api/v1/channels/{channel_id}/items/embed",
        headers=headers(owner),
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "官方预告", "note": "去原站也可以看"},
    )
    assert created.status_code == 200, created.text
    content_id = created.json()["content_id"]
    assert created.json()["status"] == "pending"
    early = client.post(
        f"/api/v1/embed/{content_id}/consent",
        headers=headers(owner),
        json={"scope": "once"},
    )
    assert early.status_code == 409

    approved = client.post(
        f"/api/v1/moderation/{content_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    listed = client.get(f"/api/v1/channels/{channel_id}/items")
    card = next(item for item in listed.json()["items"] if item["content_id"] == content_id)
    assert card["type"] == "embed"
    assert card["embed_status"] == "embeddable"
    assert card["embed_provider_code"] == "youtube"
    assert "embed_url" not in card
    loaded = client.post(
        f"/api/v1/embed/{content_id}/consent",
        headers=headers(owner),
        json={"scope": "once"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["embed_url"] == "https://www.youtube-nocookie.com/embed/abcdefghijk"

    foryou = client.get("/api/v1/me/feed?tab=foryou", headers=headers(owner))
    assert all(item["content_id"] != content_id for item in foryou.json()["items"])


def test_for_you_explains_channels_that_occur_together(client):
    viewer = register(client, "reco@example.com", "读者")
    register(client, "peer-reco@example.com", "邻居")
    client.post("/api/v1/me/regions", headers=headers(viewer), json={"region_code": "UK", "source": "manual"})
    session = client.session_factory()
    from sqlalchemy import select

    from app.models import ChannelSubscription, User

    home = Channel(code="uk-home", name_hans="家政", name_hant="家政", kind="official_auto", region_code="UK", is_active=True)
    near = Channel(code="uk-near", name_hans="邻里", name_hant="邻里", kind="official_auto", region_code="UK", is_active=True)
    far = Channel(code="uk-far", name_hans="远处", name_hant="远处", kind="official_auto", region_code="UK", is_active=True)
    session.add_all([home, near, far])
    session.flush()
    now = datetime.now(timezone.utc)
    near_post = Content(type="post", status="published", title="邻里公告", summary="一起", source_name="邻里", published_at=now)
    far_post = Content(type="post", status="published", title="远处公告", summary="单独", source_name="远处", published_at=now)
    session.add_all([near_post, far_post])
    session.flush()
    from datetime import timedelta

    session.add(ChannelItem(channel_id=near.id, content_id=near_post.id, added_at=now - timedelta(hours=2)))
    session.add(ChannelItem(channel_id=far.id, content_id=far_post.id, added_at=now))
    viewer_id = session.scalar(select(User.id).where(User.email == "reco@example.com"))
    peer_id = session.scalar(select(User.id).where(User.email == "peer-reco@example.com"))
    session.add_all(
        [
            ChannelSubscription(user_id=viewer_id, channel_id=home.id),
            ChannelSubscription(user_id=peer_id, channel_id=home.id),
            ChannelSubscription(user_id=peer_id, channel_id=near.id),
        ]
    )
    near_id = near_post.id
    far_id = far_post.id
    near_channel_id = near.id
    session.commit()
    session.close()
    feed = client.get("/api/v1/me/feed?tab=foryou", headers=headers(viewer)).json()["items"]
    order = [item["content_id"] for item in feed]
    assert order.index(near_id) < order.index(far_id)
    picked = next(item for item in feed if item["content_id"] == near_id)
    assert picked["reason_code"] == "cooccur"
    assert picked["reason"] == "和你加入的频道常一起出现"
    assert picked["channel_id"] == near_channel_id
    assert picked["channel_name"] == "邻里"
    assert picked["is_joined"] is False
    following = client.get("/api/v1/me/feed", headers=headers(viewer)).json()
    assert following["joined_count"] == 1
    by_time = client.get("/api/v1/me/feed?tab=foryou&order=time", headers=headers(viewer)).json()["items"]
    assert [item["content_id"] for item in by_time].index(far_id) < [item["content_id"] for item in by_time].index(near_id)


def test_submission_review_closed_loop(client):
    """投稿 → 房主看待审队列 → 通过/拒绝，全流程闭环。"""
    owner = register(client, "submit-owner@example.com", "房主")
    verify(client, owner, "+447700900911")
    member = register(client, "submit-member@example.com", "投稿人")
    verify(client, member, "+447700900912")

    session = client.session_factory()
    parent = Channel(
        code="uk-submit-parent",
        name_hans="投稿测试",
        name_hant="投稿測試",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(parent)
    session.commit()
    parent_id = parent.id
    session.close()

    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "投稿圈", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    assert client.put(f"/api/v1/me/subscriptions/{room_id}", headers=headers(member)).status_code == 200

    # 普通用户投稿
    submitted = client.post(
        f"/api/v1/channels/{room_id}/submissions",
        headers=headers(member),
        json={"title": "我的投稿", "body": "投稿正文"},
    )
    assert submitted.status_code == 200, submitted.text
    content_id = submitted.json()["content_id"]

    # 房主看待审队列
    queue = client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(owner))
    assert queue.status_code == 200, queue.text
    items = queue.json()["items"]
    assert queue.json()["pending_count"] == 1
    assert items[0]["content_id"] == content_id
    assert items[0]["title"] == "我的投稿"

    # 非房主/非协作者不能看待审队列
    assert client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(member)).status_code == 404

    # 房主通过投稿
    decided = client.post(
        f"/api/v1/channels/{room_id}/submissions/{content_id}/decision",
        headers=headers(owner),
        json={"decision": "accept"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "published"

    # 通过后队列清空，投稿已发布可被订阅者看到
    queue_after = client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(owner)).json()
    assert queue_after["pending_count"] == 0
    stream = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(member)).json()["items"]
    assert any(item["content_id"] == content_id for item in stream)

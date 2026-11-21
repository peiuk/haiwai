"""审计修复：私信不能借别人的房源绕过、私信限流、浏览数落库、游客举报去重、协作者能看私密房间。"""
from sqlalchemy import func, select

from app.models import Channel, ChannelItem, Content, ModerationCase, User
from tests.test_rooms import headers, official_channel, register, verify


def user_id(client, email: str) -> str:
    session = client.session_factory()
    value = session.scalar(select(User.id).where(User.email == email))
    session.close()
    return value


def news(client) -> str:
    session = client.session_factory()
    channel = Channel(code="g-news-a", name_hans="新闻", name_hant="新闻", kind="official_curated", region_code="GLOBAL", is_active=True)
    session.add(channel)
    session.flush()
    content = Content(type="news", status="published", title="一条新闻", source_name="测试", licence_ref="OGL v3.0", canonical_url="https://example.com/a")
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
    session.commit()
    content_id = content.id
    session.close()
    return content_id


def test_dm_listing_must_belong_to_recipient(client):
    host = register(client, "dm-host@example.com")
    verify(client, host, "+447700900801")
    stranger = register(client, "dm-stranger@example.com")
    closed = register(client, "dm-closed@example.com")
    client.patch("/api/v1/me/prefs", headers=headers(closed), json={"dm_allow_strangers": False})
    session = client.session_factory()
    market = Channel(code="g-market-a", name_hans="市场", name_hant="市场", kind="official_curated", category="市场", region_code="GLOBAL", is_active=True)
    session.add(market)
    session.commit()
    market_id = market.id
    session.close()
    listing = client.post(
        "/api/v1/listings",
        headers=headers(host),
        json={"channel_id": market_id, "title": "书桌", "body": "九成新书桌转让", "category": "市场", "kind": "secondhand",
              "area": "伦敦", "price_amount": "40", "price_unit": "", "contact": "sms: 1", "attrs": {}},
    )
    assert listing.status_code == 200, listing.text
    listing_id = listing.json()["content_id"]
    client.post(f"/api/v1/moderation/{listing_id}/decision", headers=headers(host), json={"decision": "approve"})

    closed_id = user_id(client, "dm-closed@example.com")
    plain = client.post("/api/v1/me/messages", headers=headers(stranger), json={"to_user_id": closed_id, "body": "你好"})
    assert plain.status_code == 403
    # 原来附上别人的房源就能直接发进去
    borrowed = client.post(
        "/api/v1/me/messages", headers=headers(stranger), json={"to_user_id": closed_id, "body": "你好", "listing_id": listing_id}
    )
    assert borrowed.status_code == 404
    own = client.post(
        "/api/v1/me/messages",
        headers=headers(stranger),
        json={"to_user_id": user_id(client, "dm-host@example.com"), "body": "还在吗", "listing_id": listing_id},
    )
    assert own.status_code == 200, own.text


def test_dm_rate_limit(client):
    register(client, "dm-rl-to@example.com")
    sender = register(client, "dm-rl-from@example.com")
    opened = client.post(
        "/api/v1/me/messages", headers=headers(sender), json={"to_user_id": user_id(client, "dm-rl-to@example.com"), "body": "1"}
    )
    thread_id = opened.json()["thread_id"]
    codes = [client.post(f"/api/v1/me/messages/{thread_id}", headers=headers(sender), json={"body": "x"}).status_code for _ in range(10)]
    assert codes[:9] == [200] * 9 and codes[9] == 429


def test_view_count_is_saved(client):
    content_id = news(client)
    for _ in range(2):
        assert client.get(f"/api/v1/contents/{content_id}").status_code == 200
    session = client.session_factory()
    assert session.get(Content, content_id).view_count == 2
    # 作者自己看不算：不然刷新自己的帖子就能刷上首页排行
    author = register(client, "view-author@example.com")
    session.get(Content, content_id).author_id = user_id(client, "view-author@example.com")
    session.commit()
    assert client.get(f"/api/v1/contents/{content_id}", headers=headers(author)).status_code == 200
    session.expire_all()
    assert session.get(Content, content_id).view_count == 2
    session.close()


def test_guest_reports_reuse_open_case(client):
    content_id = news(client)
    first = client.post(f"/api/v1/contents/{content_id}/report", json={"reason": "scam"})
    second = client.post(f"/api/v1/contents/{content_id}/report", json={"reason": "scam"})
    assert first.status_code == second.status_code == 200
    session = client.session_factory()
    assert session.scalar(select(func.count()).select_from(ModerationCase).where(ModerationCase.content_id == content_id)) == 1
    session.close()


def test_collaborator_can_read_private_room(client):
    parent_id = official_channel(client)
    owner = register(client, "pr-owner@example.com")
    verify(client, owner, "+447700900811")
    editor = register(client, "pr-editor@example.com")
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "内部房间", "parent_channel_id": parent_id, "is_private": True}
    ).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    client.post(f"/api/v1/channels/{room_id}/announcements", headers=headers(owner), json={"title": "内部", "body": "成员可见"})
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(editor)).status_code == 404
    added = client.put(f"/api/v1/channels/{room_id}/collaborators/{user_id(client, 'pr-editor@example.com')}", headers=headers(owner))
    assert added.status_code == 200, added.text
    items = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(editor))
    assert items.status_code == 200 and items.json()["items"]
    assert client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(editor)).status_code == 200

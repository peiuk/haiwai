"""Private room data must stay behind server-side membership checks."""

from app.models import Channel, ChannelItem, Content


CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": email.split("@")[0], "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def private_room(client) -> tuple[str, str, str]:
    owner = register(client, "private-owner@example.com")
    client.post("/api/v1/auth/verify-phone", headers=auth(owner), json={"phone": "+447700900987", "code": "246810"})
    viewer = register(client, "private-viewer@example.com")
    verified = client.post("/api/v1/auth/verify-phone", headers=auth(viewer), json={"phone": "+447700900988", "code": "246810"})
    assert verified.status_code == 200, verified.text
    session = client.session_factory()
    parent = Channel(code="private-parent", name_hans="测试频道", name_hant="測試頻道", kind="official_curated", region_code="UK", is_active=True)
    session.add(parent)
    session.commit()
    parent_id = parent.id
    session.close()
    created = client.post(
        "/api/v1/channels",
        headers=auth(owner),
        json={"name": "私密测试房间", "parent_channel_id": parent_id, "is_private": True},
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["channel_id"]
    decision = client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=auth(owner),
        json={"decision": "approve"},
    )
    assert decision.status_code == 200, decision.text
    return room_id, owner, viewer


def test_private_room_cannot_be_joined_without_approval(client):
    room_id, owner, viewer = private_room(client)
    direct = client.put(f"/api/v1/me/subscriptions/{room_id}", headers=auth(viewer))
    assert direct.status_code == 403

    requested = client.post(f"/api/v1/channels/{room_id}/join-requests", headers=auth(viewer))
    assert requested.status_code == 200, requested.text
    waiting = client.get(f"/api/v1/channels/{room_id}", headers=auth(viewer))
    assert waiting.json()["join_request_pending"] is True
    approved = client.post(
        f"/api/v1/channels/{room_id}/join-requests/{requested.json()['request_id']}/approve",
        headers=auth(owner),
    )
    assert approved.status_code == 200, approved.text
    joined = client.get(f"/api/v1/channels/{room_id}", headers=auth(viewer))
    assert joined.json()["is_joined"] is True
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=auth(viewer)).status_code == 200


def test_search_finds_public_post_behind_many_private_matches(client):
    """私密房间里更新的同词帖子超过 20 条时，较早的公开帖照样能搜到（过滤在取前 20 条之前）。"""
    from datetime import datetime, timedelta, timezone

    room_id, _owner, _viewer = private_room(client)
    now = datetime.now(timezone.utc)
    session = client.session_factory()
    public = Content(type="post", status="published", title="撞词公开帖", summary="", published_at=now - timedelta(days=1))
    session.add(public)
    for index in range(21):
        hidden = Content(type="post", status="published", title=f"撞词私密帖{index}", summary="", published_at=now)
        session.add(hidden)
        session.flush()
        session.add(ChannelItem(channel_id=room_id, content_id=hidden.id))
    session.commit()
    public_id = public.id
    session.close()
    found = client.get("/api/v1/search", params={"q": "撞词"}).json()["contents"]
    assert [item["content_id"] for item in found] == [public_id]


def test_profile_shows_public_post_behind_many_private_posts(client):
    """主页只列最近 50 条：同一作者更新的私密房间帖子超过 50 条时，公开帖照样显示，帖子数也不算私密的。"""
    from datetime import datetime, timedelta, timezone

    from app.models import User

    room_id, owner, _viewer = private_room(client)
    now = datetime.now(timezone.utc)
    session = client.session_factory()
    author_id = session.query(User.id).filter(User.email == "private-owner@example.com").scalar()
    public = Content(type="post", status="published", author_id=author_id, title="公开帖", summary="", published_at=now - timedelta(days=1))
    public.created_at = now - timedelta(days=1)
    session.add(public)
    for index in range(51):
        hidden = Content(type="post", status="published", author_id=author_id, title=f"私密帖{index}", summary="", published_at=now)
        session.add(hidden)
        session.flush()
        session.add(ChannelItem(channel_id=room_id, content_id=hidden.id))
    session.commit()
    public_id = public.id
    session.close()
    posts = client.get(f"/api/v1/users/{author_id}/posts").json()["items"]
    assert [item["content_id"] for item in posts] == [public_id]
    assert client.get(f"/api/v1/users/{author_id}").json()["post_count"] == 1


def test_private_room_post_stays_off_home_rail_and_trending(client):
    """首页右栏排行和热门关键词：私密房间里再热的帖子也不能露出来，成员看得到。"""
    from datetime import datetime, timezone

    room_id, owner, _viewer = private_room(client)
    session = client.session_factory()
    hot = Content(
        type="post", status="published", title="私密热帖", summary="", keywords_json='["私密词"]',
        published_at=datetime.now(timezone.utc), view_count=99,
    )
    session.add(hot)
    session.flush()
    session.add(ChannelItem(channel_id=room_id, content_id=hot.id))
    session.commit()
    hot_id = hot.id
    session.close()

    def rail_ids(headers=None):
        rail = client.get("/api/v1/discover/home-rail", headers=headers or {}).json()
        return {item["content_id"] for item in rail["today"] + rail["week"]}

    assert hot_id not in rail_ids()
    assert hot_id in rail_ids(auth(owner))
    words = client.get("/api/v1/search/trending-keywords").json()["keywords"]
    assert "私密词" not in [item["keyword"] for item in words]


def test_private_room_content_is_not_public_by_id_or_search(client):
    room_id, owner, viewer = private_room(client)
    created = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=auth(owner),
        json={"title": "秘密测试标题", "body": "只有成员能读到的正文"},
    )
    assert created.status_code == 200, created.text
    content_id = created.json()["content_id"]
    session = client.session_factory()
    session.get(Content, content_id).keywords_json = '["privateauditword"]'
    session.commit()
    session.close()

    for headers in ({}, auth(viewer)):
        detail = client.get(f"/api/v1/channels/{room_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["is_private"] is True
        assert "seasons" not in detail.json()
        assert "subscriber_count" not in detail.json()
        assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers).status_code in {403, 404}
        assert client.get(f"/api/v1/contents/{content_id}", headers=headers).status_code == 404
        assert client.get(f"/api/v1/contents/{content_id}/comments", headers=headers).status_code == 404
        results = client.get("/api/v1/search", params={"q": "秘密测试标题"}, headers=headers)
        assert results.status_code == 200
        assert content_id not in {item["content_id"] for item in results.json()["contents"]}

    trending = client.get("/api/v1/search/trending-keywords")
    assert "privateauditword" not in {item["keyword"] for item in trending.json()["keywords"]}

    assert client.get(f"/api/v1/contents/{content_id}", headers=auth(owner)).status_code == 200
    pushed = client.post(f"/api/v1/channels/{room_id}/pushes/{content_id}", headers=auth(owner))
    assert pushed.status_code in {403, 409}
    reposted = client.post(
        f"/api/v1/contents/{content_id}/repost",
        headers=auth(owner),
        json={"channel_id": client.get(f"/api/v1/channels/{room_id}").json()["parent_channel_id"]},
    )
    assert reposted.status_code == 403

    # Old push records must not expose content through the public parent feed.
    parent_id = client.get(f"/api/v1/channels/{room_id}").json()["parent_channel_id"]
    session = client.session_factory()
    session.add(ChannelItem(channel_id=parent_id, content_id=content_id, origin_room_id=room_id))
    session.commit()
    session.close()
    public_items = client.get(f"/api/v1/channels/{parent_id}/items")
    assert public_items.status_code == 200
    assert content_id not in {item["content_id"] for item in public_items.json()["items"]}


def test_nonmember_cannot_publish_to_private_room(client):
    room_id, _, viewer = private_room(client)
    posted = client.post(
        "/api/v1/contents", headers=auth(viewer),
        json={"channel_id": room_id, "title": "侵入帖子", "body": "不应发进私密房间"},
    )
    assert posted.status_code == 403
    submitted = client.post(
        f"/api/v1/channels/{room_id}/submissions", headers=auth(viewer),
        json={"title": "侵入投稿", "body": "不应发进私密房间"},
    )
    assert submitted.status_code == 403


def test_owner_can_reject_private_room_join_request(client):
    room_id, owner, viewer = private_room(client)
    requested = client.post(f"/api/v1/channels/{room_id}/join-requests", headers=auth(viewer))
    request_id = requested.json()["request_id"]
    unauthorized = client.post(
        f"/api/v1/channels/{room_id}/join-requests/{request_id}/reject",
        headers=auth(viewer),
    )
    assert unauthorized.status_code == 403
    rejected = client.post(
        f"/api/v1/channels/{room_id}/join-requests/{request_id}/reject",
        headers=auth(owner),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["rejected"] is True
    assert client.get(f"/api/v1/channels/{room_id}", headers=auth(viewer)).json()["join_request_pending"] is False
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=auth(viewer)).status_code == 404
    assert client.get(f"/api/v1/channels/{room_id}/join-requests", headers=auth(owner)).json()["items"] == []
    reapplied = client.post(f"/api/v1/channels/{room_id}/join-requests", headers=auth(viewer))
    assert reapplied.status_code == 200
    assert reapplied.json()["request_id"] != request_id


def test_private_room_favorite_disappears_after_leaving(client):
    room_id, owner, viewer = private_room(client)
    content = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=auth(owner),
        json={"title": "仅成员收藏", "body": "不能在退出后继续展示"},
    )
    content_id = content.json()["content_id"]
    requested = client.post(f"/api/v1/channels/{room_id}/join-requests", headers=auth(viewer))
    client.post(
        f"/api/v1/channels/{room_id}/join-requests/{requested.json()['request_id']}/approve",
        headers=auth(owner),
    )
    liked = client.post(f"/api/v1/contents/{content_id}/favorite", headers=auth(viewer))
    assert liked.status_code == 200, liked.text
    assert content_id in {item["content_id"] for item in client.get("/api/v1/me/favorites", headers=auth(viewer)).json()["items"]}
    left = client.delete(f"/api/v1/me/subscriptions/{room_id}", headers=auth(viewer))
    assert left.status_code == 200, left.text
    assert content_id not in {item["content_id"] for item in client.get("/api/v1/me/favorites", headers=auth(viewer)).json()["items"]}

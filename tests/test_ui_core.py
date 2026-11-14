from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Channel, ChannelItem, ChannelSubscription, Content, User

from tests.test_feed import auth_header, register


def test_register_join_codes_and_refresh_rotation(client):
    session = client.session_factory()
    housing = Channel(
        code="london-housing",
        name_hans="伦敦租房",
        name_hant="倫敦租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(housing)
    session.commit()
    housing_id = housing.id
    session.close()

    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": "joiner@example.com",
            "password": "password-1",
            "display_name": "Joiner",
            "join_codes": ["london-housing", "missing-code"],
            "consents": [
                {"purpose": "tos", "version": "2026-11-08", "granted": True},
                {"purpose": "privacy", "version": "2026-11-08", "granted": True},
            ],
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["joined_channels"] == 1
    refresh = body["refresh_token"]

    subs = client.get("/api/v1/me/subscriptions", headers=auth_header(body["access_token"]))
    assert subs.status_code == 200
    assert len(subs.json()["items"]) == 1
    assert subs.json()["items"][0]["channel_id"] == housing_id

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != refresh

    stale = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert stale.status_code == 401

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
    assert logout.status_code == 200
    assert logout.json()["logged_out"] is True


def test_open_request_does_not_change_country(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "region-ask@example.com",
            "password": "password-1",
            "display_name": "用户",
            "consents": [
                {"purpose": "tos", "version": "2026-11-08", "granted": True},
                {"purpose": "privacy", "version": "2026-11-08", "granted": True},
            ],
        },
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/me/regions", headers=headers, json={"region_code": "UK", "source": "manual"})
    asked = client.post("/api/v1/me/regions/requests", headers=headers, json={"region_code": "jp"})
    assert asked.status_code == 200, asked.text
    assert asked.json()["status"] == "recorded"
    again = client.post("/api/v1/me/regions/requests", headers=headers, json={"region_code": "JP"})
    assert again.status_code == 200
    assert client.get("/api/v1/me/regions/requests", headers=headers).json()["region_codes"] == ["JP"]
    assert client.get("/api/v1/me/regions", headers=headers).json()["region_code"] == "UK"
    opened = client.post("/api/v1/me/regions/requests", headers=headers, json={"region_code": "UK"})
    assert opened.status_code == 422


def test_region_pref_feed_fields_channel_detail_and_pagination(client):
    token = register(client, email="region@example.com")
    headers = auth_header(token)

    default = client.get("/api/v1/me/regions", headers=headers)
    assert default.status_code == 200
    assert default.json()["region_code"] == "GLOBAL"

    locked = client.post(
        "/api/v1/me/regions",
        headers=headers,
        json={"region_code": "UK", "source": "manual", "locked": True},
    )
    assert locked.status_code == 200
    assert locked.json()["locked"] is True

    blocked = client.post(
        "/api/v1/me/regions",
        headers=headers,
        json={"region_code": "GLOBAL", "source": "manual"},
    )
    assert blocked.status_code == 409

    now = datetime.now(timezone.utc)
    session = client.session_factory()
    user_id = session.scalar(select(User.id).where(User.email == "region@example.com"))
    channel = Channel(
        code="uk-news",
        name_hans="英国要闻",
        name_hant="英國要聞",
        kind="official_auto",
        region_code="UK",
        is_active=True,
    )
    items: list[Content] = []
    for index in range(3):
        items.append(
            Content(
                type="news",
                status="published",
                title=f"提要 {index}",
                title_hant=f"提要 {index}",
                summary=f"摘要 {index}",
                source_name="GOV.UK",
                licence_ref="OGL v3.0",
                canonical_url=f"https://www.gov.uk/post-{index}",
                published_at=now - timedelta(minutes=index),
            )
        )
    session.add(channel)
    session.add_all(items)
    session.flush()
    session.add(ChannelSubscription(user_id=user_id, channel_id=channel.id, last_read_at=now - timedelta(hours=1)))
    for index, content in enumerate(items):
        session.add(
            ChannelItem(
                channel_id=channel.id,
                content_id=content.id,
                pinned=index == 0,
                added_at=now - timedelta(minutes=index),
            )
        )
    session.commit()
    channel_id = channel.id
    session.close()

    feed_page = client.get("/api/v1/me/feed?limit=2", headers=headers)
    assert feed_page.status_code == 200
    body = feed_page.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"]
    card = body["items"][0]
    assert card["title_hant"]
    assert card["source_name"] == "GOV.UK"
    assert card["licence_ref"] == "OGL v3.0"
    assert card["is_unread"] is True
    assert body["new_count"] == 3

    read = client.post(f"/api/v1/channels/{channel_id}/read", headers=headers)
    assert read.status_code == 200

    feed_after_read = client.get("/api/v1/me/feed", headers=headers)
    assert feed_after_read.json()["items"][0]["is_unread"] is False
    assert feed_after_read.json()["new_count"] == 0

    detail = client.get(f"/api/v1/channels/{channel_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["is_joined"] is True
    assert detail.json()["pinned_announcement_count"] == 1

    items_page = client.get(f"/api/v1/channels/{channel_id}/items?limit=2", headers=headers)
    assert items_page.status_code == 200
    assert len(items_page.json()["items"]) == 2
    assert items_page.json()["next_cursor"]

    uk_only = client.get("/api/v1/channels?region_code=UK")
    assert all(item["region_code"] == "UK" for item in uk_only.json()["items"])


def test_register_keeps_handle_and_avatar_tone(client):
    consents = [
        {"purpose": "tos", "version": "2026-11-08", "granted": True},
        {"purpose": "privacy", "version": "2026-11-08", "granted": True},
    ]
    named = client.post(
        "/api/v1/auth/register",
        json={
            "email": "pei@example.com",
            "password": "password-1",
            "display_name": "裴总",
            "handle": "@Pei_1",
            "avatar_tone": "c",
            "city_code": "伦敦",
            "consents": consents,
        },
    )
    assert named.status_code == 200, named.text
    headers = {"Authorization": f"Bearer {named.json()['access_token']}"}
    me = client.get("/api/v1/me", headers=headers).json()
    assert me["handle"] == "pei_1"
    assert me["avatar_tone"] == "c"
    assert me["city_label"] == "伦敦"
    profile = client.get(f"/api/v1/users/{me['user_id']}").json()
    assert profile["handle"] == "pei_1"
    assert profile["avatar_tone"] == "c"
    assert profile["city_label"] == "伦敦"
    moved = client.patch("/api/v1/me", headers=headers, json={"city_label": "曼城"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["city_label"] == "曼城"
    cleared = client.patch("/api/v1/me", headers=headers, json={"city_label": ""})
    assert cleared.json()["city_label"] == ""
    taken = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-pei@example.com",
            "password": "password-1",
            "display_name": "另一个",
            "handle": "pei_1",
            "consents": consents,
        },
    )
    assert taken.status_code == 409
    assert taken.json()["code"] == "DUPLICATE_HANDLE"
    auto = client.post(
        "/api/v1/auth/register",
        json={"email": "pei@other.test", "password": "password-1", "display_name": "自动", "consents": consents},
    )
    auto_headers = {"Authorization": f"Bearer {auto.json()['access_token']}"}
    assert client.get("/api/v1/me", headers=auto_headers).json()["handle"] == "pei"
    again = client.post(
        "/api/v1/auth/register",
        json={"email": "pei@third.test", "password": "password-1", "display_name": "下一个", "consents": consents},
    )
    again_headers = {"Authorization": f"Bearer {again.json()['access_token']}"}
    assert client.get("/api/v1/me", headers=again_headers).json()["handle"] == "pei1"
    renamed = client.patch(
        "/api/v1/me",
        headers=headers,
        json={"display_name": "裴先生", "handle": "@Harbour", "avatar_tone": "b"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "裴先生"
    assert renamed.json()["handle"] == "harbour"
    assert renamed.json()["avatar_tone"] == "b"
    kept = client.patch("/api/v1/me", headers=headers, json={"handle": "harbour"})
    assert kept.status_code == 200
    clash = client.patch("/api/v1/me", headers=headers, json={"handle": "pei"})
    assert clash.status_code == 409
    assert clash.json()["code"] == "DUPLICATE_HANDLE"

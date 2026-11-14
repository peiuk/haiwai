from datetime import datetime, timedelta, timezone

from app.models import Channel, ChannelItem, Content


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str = "ada@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password-1",
            "display_name": "Ada",
            "consents": [
                {"purpose": "tos", "version": "2026-11-08", "granted": True},
                {"purpose": "privacy", "version": "2026-11-08", "granted": True},
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_register_lists_public_channels_and_rejects_duplicate(client):
    token = register(client)
    created = client.session_factory()
    channel = Channel(
        code="uk-housing",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    hidden = Channel(
        code="draft-jobs",
        name_hans="未公开招聘",
        name_hant="未公開招聘",
        kind="official_auto",
        region_code="UK",
        is_active=False,
    )
    created.add_all([channel, hidden])
    created.commit()
    created.close()

    listed = client.get("/api/v1/channels")
    assert listed.status_code == 200
    codes = [item["code"] for item in listed.json()["items"]]
    assert codes == ["uk-housing"]

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "ada@example.com",
            "password": "password-1",
            "display_name": "Ada",
            "consents": [
                {"purpose": "tos", "version": "2026-11-08", "granted": True},
                {"purpose": "privacy", "version": "2026-11-08", "granted": True},
            ],
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_EMAIL"

    missing = client.get("/api/v1/me/feed")
    assert missing.status_code == 401

    logged = client.post(
        "/api/v1/auth/login",
        json={"email": "Ada@example.com", "password": "password-1"},
    )
    assert logged.status_code == 200
    assert logged.json()["access_token"]
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "nope-nope"},
    )
    assert wrong.status_code == 401
    assert token


def test_feed_is_pinned_then_time_ordered_deduped_and_respects_mute(client):
    token = register(client)
    now = datetime.now(timezone.utc)
    session = client.session_factory()
    housing = Channel(
        code="uk-housing",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    visa = Channel(
        code="uk-visa",
        name_hans="签证与政策",
        name_hant="簽證與政策",
        kind="official_auto",
        region_code="UK",
        is_active=True,
    )
    pinned = Content(
        type="post",
        status="published",
        title="押金保护说明",
        summary="押金须放入政府认可计划。",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/deposit",
    )
    newer = Content(
        type="news",
        status="published",
        title="签证费调整",
        summary="内政部公布新收费。",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/visa-fee",
    )
    shared = Content(
        type="news",
        status="published",
        title="租房合同检查清单",
        summary="签约前核对这几项。",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/tenancy",
    )
    session.add_all([housing, visa, pinned, newer, shared])
    session.flush()
    session.add_all(
        [
            ChannelItem(channel_id=housing.id, content_id=pinned.id, pinned=True, added_at=now - timedelta(hours=5)),
            ChannelItem(channel_id=visa.id, content_id=newer.id, pinned=False, added_at=now - timedelta(hours=1)),
            ChannelItem(channel_id=housing.id, content_id=shared.id, pinned=False, added_at=now - timedelta(hours=3)),
            ChannelItem(channel_id=visa.id, content_id=shared.id, pinned=False, added_at=now - timedelta(minutes=10)),
        ]
    )
    session.commit()
    housing_id, visa_id = housing.id, visa.id
    session.close()

    headers = auth_header(token)
    assert client.put(f"/api/v1/me/subscriptions/{housing_id}", headers=headers).status_code == 200
    assert client.put(f"/api/v1/me/subscriptions/{visa_id}", headers=headers).status_code == 200
    again = client.put(f"/api/v1/me/subscriptions/{housing_id}", headers=headers)
    assert again.status_code == 200
    assert again.json()["subscriber_count"] == 1

    feed = client.get("/api/v1/me/feed", headers=headers)
    assert feed.status_code == 200
    titles = [item["title"] for item in feed.json()["items"]]
    assert titles == ["押金保护说明", "租房合同检查清单", "签证费调整"]
    assert feed.json()["fresh_count"] == 0
    assert [item["show_divider_before"] for item in feed.json()["items"]] == [False, True, False]
    shared_card = feed.json()["items"][1]
    assert shared_card["channels"] == ["uk-visa", "uk-housing"]
    assert shared_card["source_name"] == "GOV.UK"
    assert shared_card["licence_ref"] == "OGL v3.0"
    assert shared_card["canonical_url"] == "https://www.gov.uk/tenancy"

    muted = client.patch(
        f"/api/v1/me/subscriptions/{housing_id}",
        headers=headers,
        json={"is_muted": True},
    )
    assert muted.status_code == 200
    muted_feed = client.get("/api/v1/me/feed", headers=headers)
    muted_titles = [item["title"] for item in muted_feed.json()["items"]]
    assert muted_titles == ["租房合同检查清单", "签证费调整"]
    assert muted_feed.json()["items"][0]["channels"] == ["uk-visa"]


def test_following_divider_counts_items_newer_than_last_seen(client):
    token = register(client, "seen@example.com")
    headers = auth_header(token)
    session = client.session_factory()
    now = datetime.now(timezone.utc)
    channel = Channel(
        code="uk-seen",
        name_hans="已看",
        name_hant="已看",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    old = Content(type="post", status="published", title="旧公告", summary="以前", source_name="来源", licence_ref="OGL")
    session.add_all([channel, old])
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=old.id, added_at=now - timedelta(hours=2)))
    channel_id = channel.id
    session.commit()
    session.close()
    assert client.put(f"/api/v1/me/subscriptions/{channel_id}", headers=headers).status_code == 200
    first = client.get("/api/v1/me/feed", headers=headers).json()
    assert first["fresh_count"] == 0
    assert first["items"][0]["show_divider_before"] is True
    assert client.post("/api/v1/me/feed/seen", headers=headers).status_code == 200
    session = client.session_factory()
    late = Content(type="post", status="published", title="新公告", summary="刚才", source_name="来源", licence_ref="OGL")
    session.add(late)
    session.flush()
    session.add(ChannelItem(channel_id=channel_id, content_id=late.id, added_at=datetime.now(timezone.utc)))
    session.commit()
    session.close()
    second = client.get("/api/v1/me/feed", headers=headers).json()
    assert second["fresh_count"] == 1
    assert second["seen_at"]
    assert [item["title"] for item in second["items"]] == ["新公告", "旧公告"]
    assert [item["show_divider_before"] for item in second["items"]] == [False, True]

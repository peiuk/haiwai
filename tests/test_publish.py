from app.models import Channel


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_channel(client, email: str = "writer@example.com") -> tuple[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password-1",
            "display_name": "作者",
            "consents": [
                {"purpose": "tos", "version": "2026-11-08", "granted": True},
                {"purpose": "privacy", "version": "2026-11-08", "granted": True},
            ],
        },
    )
    assert registered.status_code == 200, registered.text
    token = registered.json()["access_token"]
    session = client.session_factory()
    channel = Channel(
        code=f"room-{email.split('@')[0]}",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(channel)
    session.commit()
    channel_id = channel.id
    session.close()
    joined = client.put(f"/api/v1/me/subscriptions/{channel_id}", headers=auth(token))
    assert joined.status_code == 200, joined.text
    return token, channel_id


def test_first_posts_wait_for_review_before_feed(client):
    token, channel_id = register_and_channel(client)
    headers = auth(token)
    payload = {"channel_id": channel_id, "title": "Zone 2 看房记录", "body": "客厅采光可以，押金是五周。"}

    blocked = client.post("/api/v1/contents", headers=headers, json=payload)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "PHONE_NOT_VERIFIED"

    wrong = client.post(
        "/api/v1/auth/verify-phone",
        headers=headers,
        json={"phone": "+447700900111", "code": "000000"},
    )
    assert wrong.status_code == 400

    verified = client.post(
        "/api/v1/auth/verify-phone",
        headers=headers,
        json={"phone": "+447700900111", "code": "246810"},
    )
    assert verified.status_code == 200

    created = client.post("/api/v1/contents", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "pending"
    content_id = body["content_id"]

    feed = client.get("/api/v1/me/feed", headers=headers)
    assert [item["title"] for item in feed.json()["items"]] == []

    rejected = client.post(
        "/api/v1/contents",
        headers=headers,
        json={"channel_id": channel_id, "title": "广告帖", "body": "私聊领优惠码"},
    )
    rejected_id = rejected.json()["content_id"]
    decision = client.post(
        f"/api/v1/moderation/{rejected_id}/decision",
        headers=headers,
        json={"decision": "reject"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"

    approved = client.post(
        f"/api/v1/moderation/{content_id}/decision",
        headers=headers,
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "published"

    titles = [item["title"] for item in client.get("/api/v1/me/feed", headers=headers).json()["items"]]
    assert titles == ["Zone 2 看房记录"]
    card = client.get("/api/v1/me/feed", headers=headers).json()["items"][0]
    assert card["summary"] == "客厅采光可以，押金是五周。"
    assert card["source_name"] == "作者"


def test_posts_go_public_only_after_three_approved_and_hourly_cap_holds(client):
    token, channel_id = register_and_channel(client, "fourth@example.com")
    headers = auth(token)
    assert client.post(
        "/api/v1/auth/verify-phone",
        headers=headers,
        json={"phone": "+447700900222", "code": "246810"},
    ).status_code == 200

    def post(index: int):
        response = client.post(
            "/api/v1/contents",
            headers=headers,
            json={"channel_id": channel_id, "title": f"帖子{index}", "body": "正文"},
        )
        assert response.status_code == 200, response.text
        return response.json()

    # 前几条只是在等审核、没通过：第 4 条也照样要审（原来数的是全部帖子，发 3 条垃圾帖就能绕过）
    first = [post(index) for index in range(4)]
    assert [item["status"] for item in first] == ["pending"] * 4
    for item in first[:3]:
        approved = client.post(f"/api/v1/moderation/{item['content_id']}/decision", headers=headers, json={"decision": "approve"})
        assert approved.status_code == 200
    # 通过 3 条以后才直接公开
    assert post(4)["status"] == "published"

    capped = client.post(
        "/api/v1/contents",
        headers=headers,
        json={"channel_id": channel_id, "title": "第六帖", "body": "正文"},
    )
    assert capped.status_code == 429
    assert capped.json()["code"] == "RATE_LIMITED"

    titles = {item["title"] for item in client.get("/api/v1/me/feed", headers=headers).json()["items"]}
    assert titles == {"帖子0", "帖子1", "帖子2", "帖子4"}


def test_phone_requirement_can_be_switched_off_for_testing(client, monkeypatch):
    """REQUIRE_PHONE_VERIFICATION=false 时没验证手机也能发帖；默认仍然要求验证。"""
    from app.core.config import get_settings

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "nophone@example.com",
            "password": "password-1",
            "display_name": "没验证手机",
            "consents": [
                {"purpose": "tos", "version": "2026-11-08", "granted": True},
                {"purpose": "privacy", "version": "2026-11-08", "granted": True},
            ],
        },
    )
    auth = {"Authorization": "Bearer " + registered.json()["access_token"]}
    post = {"title": "测试帖", "body": "没验证手机也能发的测试帖"}

    assert client.post("/api/v1/contents", headers=auth, json=post).json()["code"] == "PHONE_NOT_VERIFIED"
    monkeypatch.setenv("REQUIRE_PHONE_VERIFICATION", "false")
    get_settings.cache_clear()
    try:
        allowed = client.post("/api/v1/contents", headers=auth, json=post)
        assert allowed.status_code == 200, allowed.text
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()

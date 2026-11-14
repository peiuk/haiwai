from sqlalchemy import select

from app.models import AuditLog, Channel, ChannelItem, Content, User


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


def test_consent_unsubscribe_unread_channel_stream_and_search(client):
    missing = client.post(
        "/api/v1/auth/register",
        json={"email": "noconsent@example.com", "password": "password-1", "display_name": "无同意", "consents": []},
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == "CONSENT_REQUIRED"

    token = register(client, "reader@example.com", "读者")
    session = client.session_factory()
    channel = Channel(
        code="uk-housing",
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

    joined = client.put(f"/api/v1/me/subscriptions/{channel_id}", headers=headers(token))
    assert joined.status_code == 200
    session = client.session_factory()
    post = Content(
        type="post",
        status="published",
        title="押金要放进保护计划",
        summary="签约前核对",
        source_name="读者",
        licence_ref="OGL",
    )
    session.add(post)
    session.flush()
    session.add(ChannelItem(channel_id=channel_id, content_id=post.id, pinned=False))
    session.commit()
    session.close()

    mine = client.get("/api/v1/me/subscriptions", headers=headers(token))
    assert mine.status_code == 200
    assert mine.json()["items"][0]["unread_count"] == 1

    stream = client.get(f"/api/v1/channels/{channel_id}/items")
    assert stream.status_code == 200
    assert stream.json()["items"][0]["title"] == "押金要放进保护计划"

    by_channel = client.get("/api/v1/search", params={"q": "租房"})
    assert by_channel.status_code == 200
    assert by_channel.json()["channels"][0]["code"] == "uk-housing"
    by_post = client.get("/api/v1/search", params={"q": "押金"})
    assert by_post.json()["contents"][0]["title"] == "押金要放进保护计划"
    assert by_post.json()["contents"][0]["licence_ref"] == "OGL"

    read = client.post(f"/api/v1/channels/{channel_id}/read", headers=headers(token))
    assert read.status_code == 200
    assert client.get("/api/v1/me/subscriptions", headers=headers(token)).json()["items"][0]["unread_count"] == 0

    left = client.delete(f"/api/v1/me/subscriptions/{channel_id}", headers=headers(token))
    assert left.status_code == 200
    assert client.get("/api/v1/me/subscriptions", headers=headers(token)).json()["items"] == []
    assert client.get("/api/v1/me/feed", headers=headers(token)).json()["items"] == []


def test_report_removes_content_and_dsar_erases_account(client):
    author = register(client, "author@example.com", "作者")
    reporter = register(client, "reporter@example.com", "举报人")
    session = client.session_factory()
    channel = Channel(
        code="uk-visa",
        name_hans="签证与政策",
        name_hant="簽證與政策",
        kind="official_auto",
        region_code="UK",
        is_active=True,
    )
    author_row = session.scalar(select(User).where(User.email == "author@example.com"))
    session.add(channel)
    session.flush()
    post = Content(
        type="post",
        status="published",
        author_id=author_row.id,
        title="虚假租房",
        summary="先转账再看房",
        source_name="作者",
    )
    session.add(post)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=post.id))
    session.commit()
    channel_id, content_id = channel.id, post.id
    session.close()

    client.put(f"/api/v1/me/subscriptions/{channel_id}", headers=headers(reporter))
    own = client.post(f"/api/v1/contents/{content_id}/report", headers=headers(author), json={"reason": "scam"})
    assert own.status_code == 403
    created = client.post(
        f"/api/v1/contents/{content_id}/report",
        headers=headers(reporter),
        json={"reason": "scam"},
    )
    assert created.status_code == 200, created.text
    case_id = created.json()["case_id"]
    again = client.post(
        f"/api/v1/contents/{content_id}/report",
        headers=headers(reporter),
        json={"reason": "scam"},
    )
    assert again.status_code == 409
    assert any(item["title"] == "虚假租房" for item in client.get("/api/v1/me/feed", headers=headers(reporter)).json()["items"])

    removed = client.post(
        f"/api/v1/moderation/cases/{case_id}/decision",
        headers=headers(reporter),
        json={"decision": "remove"},
    )
    assert removed.status_code == 200
    assert removed.json()["status"] == "deleted"
    titles = [item["title"] for item in client.get("/api/v1/me/feed", headers=headers(reporter)).json()["items"]]
    assert "虚假租房" not in titles

    session = client.session_factory()
    actions = session.scalars(select(AuditLog.action)).all()
    session.close()
    assert "content.report" in actions
    assert "moderation.remove" in actions

    exported = client.get("/api/v1/me/export", headers=headers(author))
    assert exported.status_code == 200
    assert exported.json()["user"]["email"] == "author@example.com"
    erased = client.delete("/api/v1/me", headers=headers(author))
    assert erased.status_code == 200
    login = client.post("/api/v1/auth/login", json={"email": "author@example.com", "password": "password-1"})
    assert login.status_code == 401

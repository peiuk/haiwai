from sqlalchemy import select

from app.models import AuditLog, Channel, ChannelItem, Content, User, utcnow


CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": "用户", "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_case_decision_notifies_only_the_reporter(client):
    author_token = register(client, "author-note@example.com")
    reporter_token = register(client, "reporter-note@example.com")
    session = client.session_factory()
    author = session.scalar(select(User).where(User.email == "author-note@example.com"))
    channel = Channel(
        code="uk-housing",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(channel)
    session.flush()
    removed = Content(
        type="post",
        status="published",
        author_id=author.id,
        title="可疑租房",
        summary="先转账",
        body="先转账",
        source_name=author.display_name,
        published_at=utcnow(),
    )
    kept = Content(
        type="post",
        status="published",
        author_id=author.id,
        title="普通讨论",
        summary="问问学区",
        body="问问学区",
        source_name=author.display_name,
        published_at=utcnow(),
    )
    session.add_all([removed, kept])
    session.flush()
    session.add_all(
        [
            ChannelItem(channel_id=channel.id, content_id=removed.id),
            ChannelItem(channel_id=channel.id, content_id=kept.id),
        ]
    )
    session.commit()
    removed_id, kept_id = removed.id, kept.id
    session.close()

    assert client.get("/api/v1/me/notifications", headers=headers(reporter_token)).json()["items"] == []

    scam = client.post(
        f"/api/v1/contents/{removed_id}/report",
        headers=headers(reporter_token),
        json={"reason": "scam"},
    )
    assert scam.status_code == 200, scam.text
    other = client.post(
        f"/api/v1/contents/{kept_id}/report",
        headers=headers(reporter_token),
        json={"reason": "other", "detail": "说明问题所在"},
    )
    assert other.status_code == 200, other.text

    removed_case = client.post(
        f"/api/v1/moderation/cases/{scam.json()['case_id']}/decision",
        headers=headers(author_token),
        json={"decision": "remove"},
    )
    assert removed_case.status_code == 200, removed_case.text
    dismissed = client.post(
        f"/api/v1/moderation/cases/{other.json()['case_id']}/decision",
        headers=headers(author_token),
        json={"decision": "dismiss"},
    )
    assert dismissed.status_code == 200, dismissed.text

    notes = client.get("/api/v1/me/notifications", headers=headers(reporter_token)).json()["items"]
    assert [item["body"] for item in notes] == [
        "你举报的「普通讨论」未下架",
        "你举报的「可疑租房」已下架",
    ]
    assert all(item["unread"] is True for item in notes)
    assert {item["content_id"] for item in notes} == {removed_id, kept_id}
    assert client.get("/api/v1/me/notifications", headers=headers(author_token)).json()["items"] == []

    session = client.session_factory()
    actions = set(session.scalars(select(AuditLog.action)).all())
    session.close()
    assert {"content.report", "moderation.remove", "moderation.dismiss"} <= actions

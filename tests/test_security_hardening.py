"""上线前加固：默认密钥拒绝启动、审核需要管理员、上传不能覆盖、读取有上限。"""
import pytest
from sqlalchemy import select

from app.core.config import DEFAULT_SECRET_KEY, get_settings
from app.main import create_app
from app.models import Channel, Content, User

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": "测试", "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def pending_post(client, token: str) -> str:
    session = client.session_factory()
    channel = Channel(code="uk-hardening", name_hans="加固", name_hant="加固", kind="official_curated", region_code="UK", is_active=True)
    session.add(channel)
    session.commit()
    channel_id = channel.id
    session.close()
    client.post("/api/v1/auth/verify-phone", headers=headers(token), json={"phone": "+447700900311", "code": "246810"})
    created = client.post(
        "/api/v1/contents", headers=headers(token), json={"title": "待审", "body": "待审核的帖子正文", "channel_id": channel_id}
    )
    assert created.status_code == 200, created.text
    return created.json()["content_id"]


def test_non_dev_refuses_to_start_with_default_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_SECRET_KEY", DEFAULT_SECRET_KEY)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
            create_app()
        monkeypatch.setenv("APP_SECRET_KEY", "x" * 40)
        get_settings.cache_clear()
        create_app()  # 换成自己的密钥就能启动
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_outside_dev_only_admins_can_moderate(client, monkeypatch):
    author = register(client, "author-h@example.com")
    outsider = register(client, "outsider-h@example.com")
    content_id = pending_post(client, author)

    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        denied = client.post(f"/api/v1/moderation/{content_id}/decision", headers=headers(outsider), json={"decision": "approve"})
        assert denied.status_code == 403
        session = client.session_factory()
        session.scalar(select(User).where(User.email == "outsider-h@example.com")).is_admin = True
        session.commit()
        session.close()
        allowed = client.post(f"/api/v1/moderation/{content_id}/decision", headers=headers(outsider), json={"decision": "approve"})
        assert allowed.status_code == 200, allowed.text
        session = client.session_factory()
        assert session.get(Content, content_id).status == "published"
        session.close()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def sign(client, token: str, content_type: str = "image/jpeg") -> str:
    signed = client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": content_type})
    assert signed.status_code == 200, signed.text
    return signed.json()["object_key"]


def test_stored_upload_cannot_be_overwritten(client):
    """发布并审核通过后再往同一个 key 传新文件，会让已审核的帖子悄悄换图。"""
    token = register(client, "uploader-h@example.com")
    key = sign(client, token)
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=b"\xff\xd8\xff\xe0first").status_code == 200
    again = client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=b"\xff\xd8\xff\xe0second")
    assert again.status_code == 409
    assert client.get(f"/api/v1/uploads/{key}").content == b"\xff\xd8\xff\xe0first"


def test_oversized_upload_is_rejected_by_header_before_reading(client):
    token = register(client, "bigfile-h@example.com")
    key = sign(client, token)
    too_big = client.put(
        f"/api/v1/uploads/{key}",
        headers={**headers(token), "Content-Length": str(5_000_001)},
        content=b"\xff\xd8\xff\xe0tiny",
    )
    assert too_big.status_code in {400, 413}
    # 没有真正存下来：槽位仍可再传
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=b"\xff\xd8\xff\xe0ok").status_code == 200


def test_upload_slots_per_user_are_capped(client):
    token = register(client, "slots-h@example.com")
    results = [client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": "image/png"}).status_code for _ in range(40)]
    assert 429 in results and results[0] == 200

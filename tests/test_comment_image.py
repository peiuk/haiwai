"""回复/留言支持贴一张图片 + 表情（emoji 为普通 Unicode 文本，无需后端特判）。

覆盖：
- 帖子回复带 image_key：写入 + 列表返回 image_key
- 纯图片回复（无文字）也能通过
- 无文字且无图片被拒（422/400）
- 图片必须是本人已上传的（UPLOAD_NOT_READY）
"""

from app.models import Channel, ChannelItem, Content

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str, name: str = "作者") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": name, "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def verify(client, token: str, phone: str) -> None:
    response = client.post(
        "/api/v1/auth/verify-phone",
        headers=headers(token),
        json={"phone": phone, "code": "246810"},
    )
    assert response.status_code == 200, response.text


def sign_and_store(client, token: str) -> str:
    signed = client.post(
        "/api/v1/uploads/sign",
        headers=headers(token),
        json={"content_type": "image/jpeg"},
    )
    assert signed.status_code == 200, signed.text
    key = signed.json()["object_key"]
    stored = client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=b"\xff\xd8\xff\xe0fakejpeg")
    assert stored.status_code == 200, stored.text
    return key


def setup_post(client):
    """建一个官方频道 + 一个已发布帖子，返回 (token, content_id)。"""
    session = client.session_factory()
    channel = Channel(
        code="comment-img-housing",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(channel)
    session.commit()
    channel_id = channel.id

    token = register(client, "comment-img@example.com")
    verify(client, token, "+447700901111")
    posted = client.post(
        "/api/v1/contents",
        headers=headers(token),
        json={"channel_id": channel_id, "title": "看房记录", "body": "采光不错"},
    )
    content_id = posted.json()["content_id"]
    client.post(f"/api/v1/moderation/{content_id}/decision", headers=headers(token), json={"decision": "approve"})
    return token, content_id


def test_reply_with_image_and_emoji(client):
    token, content_id = setup_post(client)
    key = sign_and_store(client, token)

    # 带文字（含 emoji）+ 图片
    replied = client.post(
        f"/api/v1/contents/{content_id}/comments",
        headers=headers(token),
        json={"body": "这采光真不错 👍😊", "image_key": key},
    )
    assert replied.status_code == 200, replied.text

    # 作者本人能看到自己的 pending 评论（含 image_key）
    listed = client.get(f"/api/v1/contents/{content_id}/comments", headers=headers(token)).json()["items"]
    assert listed[0]["body"] == "这采光真不错 👍😊"
    assert listed[0]["image_key"] == key


def test_reply_image_only(client):
    token, content_id = setup_post(client)
    key = sign_and_store(client, token)

    # 纯图片、无文字
    replied = client.post(
        f"/api/v1/contents/{content_id}/comments",
        headers=headers(token),
        json={"body": "", "image_key": key},
    )
    assert replied.status_code == 200, replied.text
    listed = client.get(f"/api/v1/contents/{content_id}/comments", headers=headers(token)).json()["items"]
    assert listed[0]["image_key"] == key


def test_reply_rejects_empty_and_foreign_image(client):
    token, content_id = setup_post(client)

    # 无文字且无图片
    empty = client.post(
        f"/api/v1/contents/{content_id}/comments",
        headers=headers(token),
        json={"body": "   "},
    )
    assert empty.status_code in (400, 422), empty.text

    # 引用一个不存在的 image_key
    foreign = client.post(
        f"/api/v1/contents/{content_id}/comments",
        headers=headers(token),
        json={"body": "带图", "image_key": "not-a-real-key"},
    )
    assert foreign.status_code == 400, foreign.text
    assert foreign.json()["code"] == "UPLOAD_NOT_READY"

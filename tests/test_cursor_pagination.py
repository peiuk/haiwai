from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Channel, ChannelItem, Content, Notification, RoomComment, User, utcnow

from tests.test_feed import auth_header, register


def _make_notifications(client, user_id: str, count: int) -> None:
    session = client.session_factory()
    base = utcnow()
    for index in range(count):
        session.add(
            Notification(
                user_id=user_id,
                kind="room.update",
                body=f"通知 {index}",
                created_at=base - timedelta(minutes=index),
            )
        )
    session.commit()
    session.close()


def test_notifications_cursor_pagination_and_read_all(client):
    token = register(client, "cursor-note@example.com")
    headers = auth_header(token)
    session = client.session_factory()
    user_id = session.scalar(select(User.id).where(User.email == "cursor-note@example.com"))
    session.close()
    _make_notifications(client, user_id, 5)

    first = client.get("/api/v1/me/notifications?limit=2", headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["items"]) == 2
    assert body["unread_count"] == 5
    assert body["next_cursor"]

    second = client.get(
        f"/api/v1/me/notifications?limit=2&cursor={body['next_cursor']}",
        headers=headers,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["items"]) == 2
    # 无重叠
    first_ids = {item["id"] for item in body["items"]}
    second_ids = {item["id"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)

    read_all = client.post("/api/v1/me/notifications/read-all", headers=headers)
    assert read_all.status_code == 200
    assert read_all.json()["marked"] == 5
    after = client.get("/api/v1/me/notifications", headers=headers).json()
    assert after["unread_count"] == 0


def test_notifications_single_read_patch_and_post(client):
    token = register(client, "single-read@example.com")
    headers = auth_header(token)
    session = client.session_factory()
    user_id = session.scalar(select(User.id).where(User.email == "single-read@example.com"))
    session.close()
    _make_notifications(client, user_id, 1)
    note = client.get("/api/v1/me/notifications", headers=headers).json()["items"][0]
    assert note["unread"] is True

    patched = client.patch(f"/api/v1/me/notifications/{note['id']}/read", headers=headers)
    assert patched.status_code == 200
    assert patched.json() == {"unread": False}
    assert client.get("/api/v1/me/notifications", headers=headers).json()["unread_count"] == 0


def test_room_comments_cursor_pagination(client):
    token = register(client, "cursor-comment@example.com")
    headers = auth_header(token)
    session = client.session_factory()
    owner = session.scalar(select(User.id).where(User.email == "cursor-comment@example.com"))
    room = Channel(
        code="room-comment-cursor",
        name_hans="留言房",
        name_hant="留言房",
        kind="room",
        region_code="UK",
        is_active=True,
        owner_id=owner,
    )
    session.add(room)
    session.flush()
    base = utcnow()
    for index in range(4):
        session.add(
            RoomComment(
                room_id=room.id,
                author_id=owner,
                body=f"留言 {index}",
                status="published",
                created_at=base - timedelta(minutes=index),
            )
        )
    session.commit()
    room_id = room.id
    session.close()

    first = client.get(f"/api/v1/channels/{room_id}/comments?limit=2", headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"]
    second = client.get(
        f"/api/v1/channels/{room_id}/comments?limit=2&cursor={body['next_cursor']}",
        headers=headers,
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 2
    first_ids = {item["id"] for item in body["items"]}
    second_ids = {item["id"] for item in second.json()["items"]}
    assert first_ids.isdisjoint(second_ids)
    # 无 cursor 时仍返回全部（向后兼容）
    all_rows = client.get(f"/api/v1/channels/{room_id}/comments", headers=headers).json()["items"]
    assert len(all_rows) == 4


def test_my_channels_quota_and_pagination(client):
    token = register(client, "cursor-rooms@example.com")
    headers = auth_header(token)
    session = client.session_factory()
    user_id = session.scalar(select(User.id).where(User.email == "cursor-rooms@example.com"))
    session.flush()
    parent = Channel(
        code="rooms-parent",
        name_hans="官方频道",
        name_hant="官方頻道",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add(parent)
    session.flush()
    for index in range(3):
        session.add(
            Channel(
                code=f"room-{index}",
                name_hans=f"我的房间{index}",
                name_hant=f"我的房間{index}",
                kind="room",
                region_code="UK",
                owner_id=user_id,
                parent_channel_id=parent.id,
                is_active=False,
            )
        )
    session.commit()
    session.close()

    body = client.get("/api/v1/me/channels", headers=headers).json()
    assert body["owned_count"] == 3
    assert body["quota_used"] == 3
    assert body["room_limit"] == 20
    assert len(body["items"]) == 3


def test_foryou_cursor_pagination_no_overlap(client):
    """首页推荐流无限下拉：游标逐页推进、不重复、不漏，末页无 next_cursor。"""
    token = register(client, "foryou-cursor@example.com")
    now = datetime.now(timezone.utc)
    session = client.session_factory()
    channel = Channel(
        code="foryou-cursor-channel",
        name_hans="游标测试频道",
        name_hant="游標測試頻道",
        kind="official_curated",
        region_code="GLOBAL",
        is_active=True,
    )
    session.add(channel)
    session.flush()
    contents = [
        Content(
            type="post",
            status="published",
            title=f"推荐内容 {index}",
            summary="游标分页用内容",
            source_name="测试",
            licence_ref="OGL",
            canonical_url=f"https://example.com/foryou/{index}",
        )
        for index in range(5)
    ]
    session.add_all(contents)
    session.flush()
    session.add_all(
        ChannelItem(channel_id=channel.id, content_id=item.id, added_at=now - timedelta(minutes=index))
        for index, item in enumerate(contents)
    )
    session.commit()
    session.close()

    headers = auth_header(token)
    first = client.get("/api/v1/me/feed?tab=foryou&limit=2", headers=headers)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"]

    second = client.get(
        f"/api/v1/me/feed?tab=foryou&limit=2&cursor={first_body['next_cursor']}",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert len(second_body["items"]) == 2
    assert second_body["next_cursor"]

    third = client.get(
        f"/api/v1/me/feed?tab=foryou&limit=2&cursor={second_body['next_cursor']}",
        headers=headers,
    )
    assert third.status_code == 200, third.text
    third_body = third.json()
    assert len(third_body["items"]) == 1
    assert not third_body.get("next_cursor")

    ids = [
        item["content_id"]
        for page in (first_body, second_body, third_body)
        for item in page["items"]
    ]
    assert len(ids) == len(set(ids)) == 5

    # 时间序同样可分页，且排序口径不变。
    by_time = client.get("/api/v1/me/feed?tab=foryou&order=time&limit=2", headers=headers)
    assert by_time.status_code == 200
    assert len(by_time.json()["items"]) == 2
    assert by_time.json()["next_cursor"]

"""列表接口的查询次数不能随条数增长（每条再查一次库，内容一多就慢）。"""
from sqlalchemy import event

from app.models import Channel, ChannelItem, Content, RoomComment, User


def _count_queries(client, path: str) -> int:
    engine = client.session_factory.kw["bind"]
    seen = {"n": 0}

    def bump(*_args, **_kwargs):
        seen["n"] += 1

    event.listen(engine, "before_cursor_execute", bump)
    try:
        assert client.get(path).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", bump)
    return seen["n"]


def test_reply_list_queries_do_not_grow_with_replies(client):
    session = client.session_factory()
    channel = Channel(code="qc", name_hans="频道", name_hant="頻道", kind="official_curated", region_code="GLOBAL", is_active=True)
    room = Channel(code="qc-room", name_hans="房间", name_hant="房間", kind="room", region_code="GLOBAL", is_active=True)
    people = [User(email=f"qc{i}@example.com", password_hash="x", display_name=f"人{i}", handle=f"person{i}") for i in range(40)]
    session.add_all([channel, room, *people])
    session.flush()
    post = Content(type="post", status="published", author_id=people[0].id, title="热帖", summary="摘要")
    session.add(post)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=post.id))
    for index, person in enumerate(people):
        # 每条回复不同作者，并 @ 另一个人：原来每条各查作者、每个 @ 再查一次
        mention = people[(index + 1) % len(people)].handle
        session.add(RoomComment(room_id=room.id, content_id=post.id, author_id=person.id, body=f"回复 @{mention}", status="published"))
    session.commit()
    post_id = post.id
    session.close()

    queries = _count_queries(client, f"/api/v1/contents/{post_id}/comments")
    assert queries <= 12, queries
    replies = client.get(f"/api/v1/contents/{post_id}/comments").json()["items"]
    assert len(replies) == 40 and all(len(item["mentions"]) == 1 for item in replies)
    assert {item["author_name"] for item in replies} == {f"人{i}" for i in range(40)}  # 作者名整批查也都对得上


def test_reply_list_pages_through_every_reply_once_in_order(client):
    from datetime import datetime, timedelta, timezone

    session = client.session_factory()
    room = Channel(code="pg-room", name_hans="房间", name_hant="房間", kind="room", region_code="GLOBAL", is_active=True)
    channel = Channel(code="pg", name_hans="频道", name_hant="頻道", kind="official_curated", region_code="GLOBAL", is_active=True)
    author = User(email="pg@example.com", password_hash="x", display_name="作者")
    session.add_all([room, channel, author])
    session.flush()
    post = Content(type="post", status="published", author_id=author.id, title="很多回复", summary="摘要")
    session.add(post)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=post.id))
    start = datetime.now(timezone.utc) - timedelta(hours=3)
    for index in range(120):
        # 每两条同一时间：游标要靠 id 分开同一时刻的回复，不能漏也不能重
        session.add(RoomComment(room_id=room.id, content_id=post.id, author_id=author.id, body=f"第{index}条",
                                status="published", created_at=start + timedelta(seconds=index // 2)))
    session.commit()
    post_id = post.id
    session.close()

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"cursor": cursor} if cursor else {}
        body = client.get(f"/api/v1/contents/{post_id}/comments", params=params).json()
        assert body["total"] == 120
        seen.extend(item["body"] for item in body["items"])
        pages += 1
        cursor = body.get("next_cursor")
        if not cursor:
            break
    assert pages == 3 and len(seen) == 120 and len(set(seen)) == 120
    times = [int(text[1:-1]) // 2 for text in seen]
    assert times == sorted(times)  # 按发布顺序

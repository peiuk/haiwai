from sqlalchemy import select

from app.models import AuditLog, Channel, Content, RoomComment, User


CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password-1", "display_name": "房主", "consents": CONSENTS},
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


def official_channel(client) -> str:
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
    return channel_id


def test_erasing_account_takes_rooms_offline_and_deletes_uploads(client):
    """「删除账号」承诺删除资料、帖子和房间：房间不再公开，上传文件连磁盘一起删。"""
    from app.models import RefreshSession, UploadObject

    owner = register(client, "erase-owner@example.com")
    verify(client, owner, "+447700900299")
    parent_id = official_channel(client)
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "待注销房间", "parent_channel_id": parent_id}
    ).json()["channel_id"]
    approved = client.post(
        f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"}
    )
    assert approved.status_code == 200, approved.text
    assert client.get(f"/api/v1/channels/{room_id}").status_code == 200

    key = client.post("/api/v1/uploads/sign", headers=headers(owner), json={"content_type": "image/jpeg"}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(owner), content=b"\xff\xd8\xff\xe0fakejpeg").status_code == 200
    assert client.get(f"/api/v1/uploads/{key}").status_code == 200

    assert client.delete("/api/v1/me", headers=headers(owner)).status_code == 200

    assert client.get(f"/api/v1/channels/{room_id}").status_code == 404
    assert client.get(f"/api/v1/uploads/{key}").status_code == 404
    session = client.session_factory()
    assert session.get(UploadObject, key) is None
    # 注册时发的刷新令牌记录也被清掉（访问令牌本身在删号后立刻失效）
    assert session.scalar(select(RefreshSession.id).join(User, User.id == RefreshSession.user_id).where(User.email.like("erased-%"))) is None
    assert client.get("/api/v1/me", headers=headers(owner)).status_code == 401
    session.close()


def test_room_needs_official_parent_then_announce_and_accept(client):
    owner = register(client, "owner-room@example.com")
    verify(client, owner, "+447700900201")
    parent_id = official_channel(client)

    official_name = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "英国官方租房", "parent_channel_id": parent_id},
    )
    assert official_name.status_code == 422
    missing = client.post("/api/v1/channels", headers=headers(owner), json={"name": "伦敦看房笔记"})
    assert missing.status_code == 422

    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "伦敦看房笔记", "parent_channel_id": parent_id},
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["channel_id"]
    assert created.json()["review_status"] == "pending"
    assert created.json()["room_type"] == "general"
    mine = client.get("/api/v1/me/channels", headers=headers(owner)).json()["items"]
    owned = next(item for item in mine if item["channel_id"] == room_id)
    assert owned["review_status"] == "pending"
    assert owned["room_type"] == "general"
    assert owned["is_active"] is False
    listed = client.get("/api/v1/channels").json()["items"]
    assert room_id not in {item["id"] for item in listed}
    assert client.get(f"/api/v1/channels/{room_id}").status_code == 404
    preview = client.get(f"/api/v1/channels/{room_id}", headers=headers(owner))
    assert preview.status_code == 200, preview.text
    assert preview.json()["review_status"] == "pending"
    assert preview.json()["is_owner"] is True
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()["items"] == []
    editor = register(client, "pending-editor@example.com")
    session = client.session_factory()
    editor_id = session.scalar(select(User.id).where(User.email == "pending-editor@example.com"))
    session.close()
    added = client.put(f"/api/v1/channels/{room_id}/collaborators/{editor_id}", headers=headers(owner))
    assert added.status_code == 200, added.text
    opened = client.get(f"/api/v1/channels/{room_id}", headers=headers(editor))
    assert opened.status_code == 200, opened.text
    assert opened.json()["is_owner"] is False
    assert opened.json()["review_status"] == "pending"

    early = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "看房时间改到周日", "body": "周日下午两点在车站集合。"},
    )
    assert early.status_code == 200, early.text
    assert early.json()["status"] == "pending"
    draft = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()["items"]
    assert draft[0]["title"] == "看房时间改到周日"
    assert draft[0]["status"] == "pending"
    assert client.get(f"/api/v1/channels/{room_id}/items").status_code == 404

    approved = client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/api/v1/channels/{room_id}")
    assert detail.json()["room_type"] == "general"
    assert detail.json()["room_type_label"] == "通用"  # 页面上显示中文名，不能露出英文代号
    changed = client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"room_type": "series"})
    assert changed.status_code == 200
    changed_detail = client.get(f"/api/v1/channels/{room_id}").json()
    assert changed_detail["room_type"] == "series" and changed_detail["room_type_label"] == "剧集"
    rejected = client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"room_type": "drama"})
    assert rejected.status_code == 422
    empty = client.get("/api/v1/channels?kind=room").json()["items"]
    assert room_id not in {item["id"] for item in empty}
    hidden = client.get("/api/v1/search", params={"q": "伦敦看房笔记"}).json()["channels"]
    assert room_id not in {item["id"] for item in hidden}

    announced = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "看房时间改到周日", "body": "周日下午两点在车站集合。"},
    )
    assert announced.status_code == 200, announced.text
    listed = client.get("/api/v1/channels?kind=room").json()["items"]
    room = next(item for item in listed if item["id"] == room_id)
    assert room["parent_channel_id"] == parent_id
    assert room["region_code"] == "UK"

    guest = register(client, "guest-room@example.com")
    verify(client, guest, "+447700900202")
    submitted = client.post(
        f"/api/v1/channels/{room_id}/submissions",
        headers=headers(guest),
        json={"title": "Canary Wharf 两居", "body": "近车站，押金五周。"},
    )
    assert submitted.status_code == 200, submitted.text
    submission_id = submitted.json()["content_id"]
    before = client.get(f"/api/v1/channels/{room_id}/items").json()["items"]
    assert [item["title"] for item in before] == ["看房时间改到周日"]
    assert before[0]["pinned"] is True
    assert submission_id not in {item["content_id"] for item in before}

    accepted = client.post(
        f"/api/v1/channels/{room_id}/submissions/{submission_id}/decision",
        headers=headers(owner),
        json={"decision": "accept"},
    )
    assert accepted.status_code == 200, accepted.text
    after = client.get(f"/api/v1/channels/{room_id}/items").json()["items"]
    assert [item["title"] for item in after] == ["看房时间改到周日", "Canary Wharf 两居"]

    nested = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "不能挂房间", "parent_channel_id": room_id},
    )
    assert nested.status_code == 400
    assert nested.json()["code"] == "PARENT_REQUIRED"

    session = client.session_factory()
    actions = set(session.scalars(select(AuditLog.action)).all())
    session.close()
    assert {
        "channel.create",
        "channel.approve",
        "announcement.create",
        "submission.create",
        "submission.accept",
    } <= actions


def test_collaborator_can_edit_but_not_manage(client):
    owner = register(client, "collab-owner@example.com")
    verify(client, owner, "+447700900214")
    editor = register(client, "collab-editor@example.com")
    parent_id = official_channel(client)
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "协编房间", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    session = client.session_factory()
    from sqlalchemy import select

    from app.models import User

    editor_id = session.scalar(select(User.id).where(User.email == "collab-editor@example.com"))
    session.close()
    added = client.put(f"/api/v1/channels/{room_id}/collaborators/{editor_id}", headers=headers(owner))
    assert added.status_code == 200
    detail = client.get(f"/api/v1/channels/{room_id}").json()
    assert detail["owner"]["role"] == "owner"
    assert detail["owner"]["handle"] == "collabowner"
    assert detail["owner"]["avatar_tone"] == "a"
    assert detail["parent_name_hans"] == "英国租房"
    assert detail["collaborators"][0]["user_id"] == editor_id
    assert detail["collaborators"][0]["handle"] == "collabeditor"
    assert detail["collaborators"][0]["display_name"] == "房主"
    announced = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(editor),
        json={"title": "协作者公告", "body": "今晚更新片单"},
    )
    assert announced.status_code == 200, announced.text
    denied = client.put(f"/api/v1/channels/{room_id}/collaborators/{editor_id}", headers=headers(editor))
    assert denied.status_code == 404
    removed = client.delete(f"/api/v1/channels/{room_id}/collaborators/{editor_id}", headers=headers(owner))
    assert removed.status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}").json()["collaborators"] == []


def test_owner_stops_at_room_limit(client):
    owner = register(client, "limit-room@example.com")
    verify(client, owner, "+447700900203")
    parent_id = official_channel(client)
    for index in range(20):
        created = client.post(
            "/api/v1/channels",
            headers=headers(owner),
            json={"name": f"房间{index}", "parent_channel_id": parent_id},
        )
        assert created.status_code == 200, created.text
    blocked = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "第21个房间", "parent_channel_id": parent_id},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "CHANNEL_LIMIT"


def test_series_order_and_private_progress(client):
    owner = register(client, "series@example.com")
    verify(client, owner, "+447700900211")
    viewer = register(client, "viewer-series@example.com")
    parent_id = official_channel(client)
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "新闻女王", "parent_channel_id": parent_id, "room_type": "series"},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    later = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "第二集", "body": "第二集内容", "season": 1, "episode": 2},
    )
    earlier = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "第一集", "body": "第一集内容", "season": 1, "episode": 1},
    )
    assert later.json()["sort_key"] == "S01E002"
    assert earlier.json()["sort_key"] == "S01E001"
    first_id = earlier.json()["content_id"]

    def titles() -> list[str]:
        rows = client.get(f"/api/v1/channels/{room_id}/items").json()["items"]
        return [row["title"] for row in rows]

    assert titles() == ["第一集", "第二集"]
    moved = client.post(
        f"/api/v1/channels/{room_id}/entries/{first_id}/move",
        headers=headers(owner),
        json={"direction": "down"},
    )
    assert moved.status_code == 200
    assert titles() == ["第二集", "第一集"]
    restored = client.post(f"/api/v1/channels/{room_id}/entries/reorder", headers=headers(owner))
    assert restored.json()["reordered"] == 2
    assert titles() == ["第一集", "第二集"]
    later_season = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "第二季第一集", "body": "新一季", "season": 2, "episode": 1},
    )
    assert later_season.status_code == 200, later_season.text
    detail = client.get(f"/api/v1/channels/{room_id}").json()
    assert detail["seasons"] == [1, 2]
    assert detail["sort_basis"] == "按集号"
    second = client.get(f"/api/v1/channels/{room_id}/items?season=2").json()["items"]
    assert [item["title"] for item in second] == ["第二季第一集"]
    saved = client.put(
        f"/api/v1/channels/{room_id}/items/{first_id}/progress",
        headers=headers(viewer),
        json={"progress": 40},
    )
    assert saved.json()["progress"] == 40
    owner_list = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()
    viewer_list = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(viewer)).json()
    assert viewer_list["progress_scope"] == "self"
    assert viewer_list["sort_basis"] == "按集号"
    owner_row = next(row for row in owner_list["items"] if row["content_id"] == first_id)
    viewer_row = next(row for row in viewer_list["items"] if row["content_id"] == first_id)
    assert owner_row["progress"] is None
    assert viewer_row["progress"] == 40


def test_film_entry_keeps_year(client):
    owner = register(client, "film-room@example.com")
    verify(client, owner, "+447700900213")
    viewer = register(client, "film-viewer@example.com")
    parent_id = official_channel(client)
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "片单", "parent_channel_id": parent_id, "room_type": "film"},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    missing = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "新闻女王", "body": "想看"},
    )
    assert missing.status_code == 400
    added = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "新闻女王", "body": "想看", "year": 2023},
    )
    assert added.status_code == 200, added.text
    row = client.get(f"/api/v1/channels/{room_id}/items").json()["items"][0]
    assert row["year"] == 2023
    assert row["sort_key"] == "F0001"
    content_id = added.json()["content_id"]
    saved = client.put(
        f"/api/v1/channels/{room_id}/items/{content_id}/progress",
        headers=headers(viewer),
        json={"progress": 100, "watch_mark": "watched"},
    )
    assert saved.json()["watch_mark"] == "watched"
    owner_row = next(item for item in client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()["items"] if item["content_id"] == content_id)
    viewer_row = next(item for item in client.get(f"/api/v1/channels/{room_id}/items", headers=headers(viewer)).json()["items"] if item["content_id"] == content_id)
    assert owner_row["watch_mark"] is None
    assert viewer_row["watch_mark"] == "watched"


def test_video_entry_requires_rights_confirmation(client):
    owner = register(client, "video-room@example.com")
    verify(client, owner, "+447700900212")
    parent_id = official_channel(client)
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "原创短片", "parent_channel_id": parent_id, "room_type": "video"},
    )
    room_id = created.json()["channel_id"]
    assert client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    blocked = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "街头", "body": "自己拍的"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "RIGHTS_REQUIRED"
    added = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "街头", "body": "自己拍的", "rights_confirmed": True},
    )
    assert added.status_code == 200, added.text
    assert added.json()["sort_key"] == "V0001"
    row = client.get(f"/api/v1/channels/{room_id}/items").json()["items"][0]
    assert row["rights_confirmed"] is True


def test_wrong_country_hides_room_and_author_sees_pending(client):
    parent_id = official_channel(client)
    owner = register(client, "guard-owner@example.com")
    verify(client, owner, "+447700900301")
    viewer = register(client, "guard-viewer@example.com")
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "伦敦剧", "parent_channel_id": parent_id, "room_type": "series"},
    )
    room_id = created.json()["channel_id"]
    approved = client.post(
        f"/api/v1/moderation/channels/{room_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    posted = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": room_id, "title": "待审", "body": "还在审核"},
    )
    assert posted.status_code == 200, posted.text
    content_id = posted.json()["content_id"]
    author_items = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()["items"]
    assert author_items[0]["content_id"] == content_id
    assert author_items[0]["status"] == "pending"
    assert author_items[0]["comment_count"] == 0
    assert client.get(f"/api/v1/channels/{room_id}/items").json()["items"] == []

    session = client.session_factory()
    author = session.scalar(select(User).where(User.email == "guard-owner@example.com"))
    content = session.get(Content, content_id)
    content.status = "published"
    session.add(RoomComment(room_id=room_id, content_id=content_id, author_id=author.id, body="讨论一下", status="published"))
    session.commit()
    session.close()
    published = client.get(f"/api/v1/channels/{room_id}/items").json()["items"][0]
    assert published["status"] == "published"
    assert published["comment_count"] == 1

    client.post("/api/v1/me/regions", headers=headers(viewer), json={"region_code": "GLOBAL", "source": "manual"})
    detail = client.get(f"/api/v1/channels/{room_id}", headers=headers(viewer)).json()
    assert detail["region_blocked"] is True
    assert detail["name_hans"] == "伦敦剧"
    assert detail["parent_name_hans"] == "英国租房"
    assert detail["owner"]["handle"] == "guardowner"
    assert detail["rooms"] == []
    assert detail["seasons"] == []
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(viewer)).json()["items"] == []
    blocked_join = client.put(f"/api/v1/me/subscriptions/{room_id}", headers=headers(viewer))
    assert blocked_join.status_code == 403
    assert blocked_join.json()["code"] == "REGION_BLOCKED"
    blocked_comment = client.post(
        f"/api/v1/channels/{room_id}/comments",
        headers=headers(viewer),
        json={"body": "想加入讨论"},
    )
    assert blocked_comment.status_code == 403
    assert blocked_comment.json()["code"] == "REGION_BLOCKED"


def test_parent_channel_lists_rooms_and_pushed_posts_name_the_room(client):
    parent_id = official_channel(client)
    owner = register(client, "rooms-owner@example.com")
    verify(client, owner, "+447700900311")
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "空房间", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    hidden = client.get(f"/api/v1/channels/{parent_id}").json()["rooms"]
    assert hidden == []
    owned = client.get(f"/api/v1/channels/{parent_id}", headers=headers(owner)).json()["rooms"]
    assert owned[0]["id"] == room_id
    assert owned[0]["has_published"] is False
    announced = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "第一条", "body": "公开了"},
    )
    content_id = announced.json()["content_id"]
    public = client.get(f"/api/v1/channels/{parent_id}").json()["rooms"]
    assert public[0]["id"] == room_id
    assert public[0]["has_published"] is True
    private = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "只给成员", "parent_channel_id": parent_id, "is_private": True},
    )
    private_id = private.json()["channel_id"]
    client.post(
        f"/api/v1/moderation/channels/{private_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    client.post(
        f"/api/v1/channels/{private_id}/announcements",
        headers=headers(owner),
        json={"title": "内部", "body": "不公开"},
    )
    guest_ids = [item["id"] for item in client.get(f"/api/v1/channels/{parent_id}").json()["rooms"]]
    owner_ids = [item["id"] for item in client.get(f"/api/v1/channels/{parent_id}", headers=headers(owner)).json()["rooms"]]
    assert private_id not in guest_ids
    assert private_id in owner_ids
    pushed = client.post(f"/api/v1/channels/{room_id}/pushes/{content_id}", headers=headers(owner))
    assert pushed.status_code == 200, pushed.text
    card = client.get(f"/api/v1/channels/{parent_id}/items").json()["items"][0]
    assert card["origin_room_id"] == room_id
    assert card["origin_room_name"] == "空房间"


def test_report_room_and_comment(client):
    parent_id = official_channel(client)
    owner = register(client, "report-owner@example.com")
    verify(client, owner, "+447700900321")
    viewer = register(client, "report-viewer@example.com")
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "可举报", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "公开", "body": "给大家看"},
    )
    own = client.post(f"/api/v1/channels/{room_id}/report", headers=headers(owner), json={"reason": "scam"})
    assert own.status_code == 403
    short = client.post(
        f"/api/v1/channels/{room_id}/report",
        headers=headers(viewer),
        json={"reason": "other", "detail": "短"},
    )
    assert short.status_code == 422
    filed = client.post(f"/api/v1/channels/{room_id}/report", headers=headers(viewer), json={"reason": "scam"})
    assert filed.status_code == 200, filed.text
    assert filed.json()["reason_text"] == "诈骗、虚假信息或可疑交易"
    assert filed.json()["sla"] == "违法内容 24 小时内处理"
    guest = client.post(f"/api/v1/channels/{room_id}/report", json={"reason": "privacy"})
    assert guest.status_code == 200, guest.text
    mine = client.get("/api/v1/me/reports", headers=headers(viewer)).json()["items"]
    assert mine[0]["case_id"] == filed.json()["case_id"]
    again = client.post(
        f"/api/v1/channels/{room_id}/report",
        headers=headers(viewer),
        json={"reason": "other", "detail": "说明问题所在"},
    )
    assert again.status_code == 409
    comment = client.post(
        f"/api/v1/channels/{room_id}/comments",
        headers=headers(viewer),
        json={"body": "这条留言"},
    )
    comment_id = comment.json()["comment_id"]
    session = client.session_factory()
    stored = session.get(RoomComment, comment_id)
    stored.status = "published"
    session.commit()
    session.close()
    hidden = client.post(
        f"/api/v1/channels/{room_id}/comments/{comment_id}/report",
        headers=headers(viewer),
        json={"reason": "scam"},
    )
    assert hidden.status_code == 403
    comment_case = client.post(
        f"/api/v1/channels/{room_id}/comments/{comment_id}/report",
        headers=headers(owner),
        json={"reason": "scam"},
    )
    assert comment_case.status_code == 200, comment_case.text
    removed_comment = client.post(
        f"/api/v1/moderation/cases/{comment_case.json()['case_id']}/decision",
        headers=headers(owner),
        json={"decision": "remove"},
    )
    assert removed_comment.status_code == 200, removed_comment.text
    assert client.get(f"/api/v1/channels/{room_id}/comments").json()["items"] == []
    removed_room = client.post(
        f"/api/v1/moderation/cases/{filed.json()['case_id']}/decision",
        headers=headers(owner),
        json={"decision": "remove"},
    )
    assert removed_room.status_code == 200, removed_room.text
    assert client.get(f"/api/v1/channels/{room_id}").status_code == 404


def test_author_delete_removes_pushed_card(client):
    parent_id = official_channel(client)
    owner = register(client, "delete-owner@example.com")
    verify(client, owner, "+447700900341")
    other = register(client, "delete-other@example.com")
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "可删除", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    announced = client.post(
        f"/api/v1/channels/{room_id}/announcements",
        headers=headers(owner),
        json={"title": "要推上去", "body": "然后删掉"},
    )
    content_id = announced.json()["content_id"]
    pushed = client.post(f"/api/v1/channels/{room_id}/pushes/{content_id}", headers=headers(owner))
    assert pushed.status_code == 200, pushed.text
    denied = client.delete(f"/api/v1/contents/{content_id}", headers=headers(other))
    assert denied.status_code == 403
    removed = client.delete(f"/api/v1/contents/{content_id}", headers=headers(owner))
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "deleted"
    parent_ids = [item["content_id"] for item in client.get(f"/api/v1/channels/{parent_id}/items").json()["items"]]
    room_ids = [item["content_id"] for item in client.get(f"/api/v1/channels/{room_id}/items").json()["items"]]
    assert content_id not in parent_ids
    assert content_id not in room_ids
    assert client.get(f"/api/v1/contents/{content_id}").status_code == 404


def test_comment_mention_notifies_only_a_real_user(client):
    parent_id = official_channel(client)
    owner = register(client, "owner-mention@example.com")
    verify(client, owner, "+447700900351")
    mentioned = register(client, "pei@mention.test")
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "提及房间", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    posted = client.post(
        f"/api/v1/channels/{room_id}/comments",
        headers=headers(owner),
        json={"body": "你好 @pei 也看 @missing ，邮箱 me@pei.com 不算"},
    )
    assert posted.status_code == 200, posted.text
    comment_id = posted.json()["comment_id"]
    visible = client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(owner)).json()["items"][0]
    assert visible["mention_count"] == 2
    assert visible["mentions"] == ["pei"]
    assert visible["author_handle"] == "ownermention"
    quiet = client.get("/api/v1/me/notifications", headers=headers(mentioned)).json()["items"]
    assert all(item["kind"] != "mention" for item in quiet)
    approved = client.post(
        f"/api/v1/moderation/comments/{comment_id}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    still_quiet = client.get("/api/v1/me/notifications", headers=headers(mentioned)).json()["items"]
    assert all(item["kind"] != "mention" for item in still_quiet)
    liked = client.post(f"/api/v1/channels/{room_id}/comments/{comment_id}/like", headers=headers(owner))
    assert liked.status_code == 200, liked.text
    assert liked.json() == {"liked": True, "like_count": 1}
    again = client.post(f"/api/v1/channels/{room_id}/comments/{comment_id}/like", headers=headers(owner))
    assert again.json() == {"liked": False, "like_count": 0}
    client.post(f"/api/v1/channels/{room_id}/comments/{comment_id}/like", headers=headers(owner))
    seen = client.get(f"/api/v1/channels/{room_id}/comments", headers=headers(mentioned)).json()["items"][0]
    assert seen["like_count"] == 1
    assert seen["liked"] is False
    owner_id = client.get("/api/v1/me", headers=headers(owner)).json()["user_id"]
    assert client.put(f"/api/v1/me/follows/{owner_id}", headers=headers(mentioned)).status_code == 200
    second = client.post(
        f"/api/v1/channels/{room_id}/comments",
        headers=headers(owner),
        json={"body": "再 @pei 一次"},
    )
    assert client.post(
        f"/api/v1/moderation/comments/{second.json()['comment_id']}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    ).status_code == 200
    notes = client.get("/api/v1/me/notifications", headers=headers(mentioned)).json()["items"]
    assert notes[0]["kind"] == "mention"
    assert notes[0]["body"] == "房主 在留言里提到了你"
    own = client.get("/api/v1/me/notifications", headers=headers(owner)).json()["items"]
    assert all(item["kind"] != "mention" for item in own)


def test_approving_the_first_post_opens_the_room(client):
    parent_id = official_channel(client)
    owner = register(client, "first-post@example.com")
    verify(client, owner, "+447700900361")
    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "第一条房间", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    posted = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": room_id, "title": "第一篇", "body": "房间还没公开"},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "pending"
    assert client.get(f"/api/v1/channels/{room_id}").status_code == 404
    approved = client.post(
        f"/api/v1/moderation/{posted.json()['content_id']}/decision",
        headers=headers(owner),
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/api/v1/channels/{room_id}")
    assert detail.status_code == 200
    assert detail.json()["review_status"] == "approved"
    titles = [item["title"] for item in client.get(f"/api/v1/channels/{room_id}/items").json()["items"]]
    assert titles == ["第一篇"]


def test_collaborator_can_review_submissions(client):
    """协作者（非房主）可看待审投稿队列并审核通过。"""
    parent_id = official_channel(client)
    owner = register(client, "subm-owner@example.com")
    verify(client, owner, "+447700900371")
    collab = register(client, "subm-collab@example.com")
    verify(client, collab, "+447700900372")
    member = register(client, "subm-member@example.com")
    verify(client, member, "+447700900373")

    created = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": "协审房间", "parent_channel_id": parent_id},
    )
    room_id = created.json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})

    session = client.session_factory()
    collab_id = session.scalar(select(User.id).where(User.email == "subm-collab@example.com"))
    session.close()
    assert client.put(f"/api/v1/channels/{room_id}/collaborators/{collab_id}", headers=headers(owner)).status_code == 200

    assert client.put(f"/api/v1/me/subscriptions/{room_id}", headers=headers(member)).status_code == 200
    submitted = client.post(
        f"/api/v1/channels/{room_id}/submissions",
        headers=headers(member),
        json={"title": "协作者审核的投稿", "body": "正文"},
    )
    assert submitted.status_code == 200, submitted.text
    content_id = submitted.json()["content_id"]

    # 协作者能看待审队列
    queue = client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(collab))
    assert queue.status_code == 200, queue.text
    assert queue.json()["pending_count"] == 1
    assert queue.json()["items"][0]["content_id"] == content_id

    # 协作者能审核通过
    decided = client.post(
        f"/api/v1/channels/{room_id}/submissions/{content_id}/decision",
        headers=headers(collab),
        json={"decision": "accept"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "published"
    assert client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(collab)).json()["pending_count"] == 0

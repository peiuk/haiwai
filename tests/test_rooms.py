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


def admin_for(client) -> str:
    """后台接口要真管理员：房间位和推送审核都走它。"""
    from tests.test_admin import register as register_admin

    return register_admin(client, "rooms-boss@example.com", admin=True)


def approve_push(client, boss: str, content_id: str) -> None:
    done = client.post(f"/api/v1/admin/pushes/{content_id}/decision", headers=headers(boss), json={"decision": "approve"})
    assert done.status_code == 200, done.text


def set_slot(client, boss: str, channel_id: str, room_id: str):
    return client.post(f"/api/v1/admin/channels/{channel_id}/slots", headers=headers(boss), json={"room_id": room_id, "label": "推荐"})


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
    # 房间不再必须挂在频道下：不选频道也能建，国家跟着房主当前的国家
    independent = client.post("/api/v1/channels", headers=headers(owner), json={"name": "不挂频道的房间"})
    assert independent.status_code == 200, independent.text
    assert client.get("/api/v1/me/channels", headers=headers(owner)).json()["items"][0]["parent_channel_id"] is None

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
    assert detail.json()["room_type_label"] == "综合讨论"  # 页面上显示中文名，不能露出英文代号
    changed = client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"room_type": "series"})
    assert changed.status_code == 200
    changed_detail = client.get(f"/api/v1/channels/{room_id}").json()
    assert changed_detail["room_type"] == "series" and changed_detail["room_type_label"] == "剧集系列"
    # 频道页的房间列表也给中文名（原来只有 room_type，页面上露出了「general」）；房间要后台放进房间位才会出现
    boss = admin_for(client)
    assert set_slot(client, boss, parent_id, room_id).status_code == 200
    parent_rooms =client.get(f"/api/v1/channels/{changed_detail['parent_channel_id']}", headers=headers(owner)).json()["rooms"]
    assert {room["id"]: room["room_type_label"] for room in parent_rooms}[room_id] == "剧集系列"
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


def upload(client, token: str, content_type: str, data: bytes) -> str:
    key = client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": content_type}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=data).status_code == 200
    return key


def test_film_entry_needs_no_year_and_takes_cover(client):
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
    cover = upload(client, owner, "image/png", b"\x89PNG")
    clip = upload(client, owner, "video/mp4", b"\x00\x00\x00\x18ftyp")
    # 图片位不能放视频，反过来也不行
    wrong = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "新闻女王", "body": "想看", "image_keys": [clip]},
    )
    assert wrong.status_code == 400
    added = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "新闻女王", "body": "想看", "image_keys": [cover], "video_key": clip},
    )
    assert added.status_code == 200, added.text  # 不再需要年份
    row = client.get(f"/api/v1/channels/{room_id}/items").json()["items"][0]
    assert row["image_keys"] == [cover] and row["video_key"] == clip
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


def test_room_cover_set_and_cleared_by_owner_only(client):
    owner = register(client, "cover-owner@example.com")
    verify(client, owner, "+447700900214")
    other = register(client, "cover-other@example.com")
    parent_id = official_channel(client)
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "某剧", "parent_channel_id": parent_id, "room_type": "series"}
    ).json()["channel_id"]
    cover = upload(client, owner, "image/png", b"\x89PNG")
    # 别人的图片用不了；不是房主改不了
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(other), json={"cover_key": cover}).status_code in (403, 404)
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"cover_key": cover}).status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}", headers=headers(owner)).json()["cover_key"] == cover
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"cover_key": ""}).status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}", headers=headers(owner)).json()["cover_key"] is None


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
    # 原创视频不再要求勾选确认，上传即视为本人原创
    added = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "街头", "body": "自己拍的"},
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
    # 房间帖子不进后台审核，只有命中敏感词的才待审
    from app.models import BlockedTerm

    with client.session_factory() as session:
        session.add(BlockedTerm(term="待审词"))
        session.commit()
    posted = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": room_id, "title": "待审", "body": "还在审核 待审词"},
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


def test_owner_switches_room_between_private_and_public(client):
    parent_id = official_channel(client)
    owner = register(client, "switch-owner@example.com")
    verify(client, owner, "+447700900331")
    outsider = register(client, "switch-out@example.com")
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "可切换", "parent_channel_id": parent_id}).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    content_id = client.post(
        f"/api/v1/channels/{room_id}/announcements", headers=headers(owner), json={"title": "公告", "body": "大家好"}
    ).json()["content_id"]
    assert client.post(f"/api/v1/channels/{room_id}/pushes/{content_id}", headers=headers(owner)).status_code == 200
    assert client.get(f"/api/v1/channels/{parent_id}/items").json()["items"] == []  # 等审核，频道里还看不到
    approve_push(client, admin_for(client), content_id)
    assert client.get(f"/api/v1/channels/{parent_id}/items").json()["items"]

    # 改成私密：推到频道的帖子撤回，外人看不到房间内容
    switched = client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"is_private": True})
    assert switched.status_code == 200 and switched.json()["is_private"] is True
    assert client.get(f"/api/v1/channels/{parent_id}/items").json()["items"] == []
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(outsider)).status_code == 404
    assert client.post(f"/api/v1/channels/{room_id}/join-requests", headers=headers(outsider)).status_code == 200

    # 再改回公开：外人能看，待审的加入申请清掉
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(outsider), json={"is_private": False}).status_code in (403, 404)
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"is_private": False}).json()["is_private"] is False
    assert client.get(f"/api/v1/channels/{room_id}/items", headers=headers(outsider)).status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}", headers=headers(owner)).json()["is_private"] is False
    with client.session_factory() as session:
        from app.models import RoomJoinRequest

        assert session.scalar(select(RoomJoinRequest).where(RoomJoinRequest.room_id == room_id)) is None


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
    boss = admin_for(client)
    # 房间不会因为父频道自动出现在频道里，要后台放进房间位
    assert client.get(f"/api/v1/channels/{parent_id}").json()["rooms"] == []
    assert set_slot(client, boss, parent_id, room_id).status_code == 200
    listed = client.get(f"/api/v1/channels/{parent_id}").json()["rooms"]
    assert listed[0]["id"] == room_id and listed[0]["slot_label"] == "推荐"
    assert listed[0]["has_published"] is False
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
    assert set_slot(client, boss, parent_id, private_id).status_code == 404  # 私密房间不能放进公开频道的房间位
    guest_ids = [item["id"] for item in client.get(f"/api/v1/channels/{parent_id}").json()["rooms"]]
    assert private_id not in guest_ids
    pushed = client.post(f"/api/v1/channels/{room_id}/pushes/{content_id}", headers=headers(owner))
    assert pushed.status_code == 200 and pushed.json()["status"] == "pending", pushed.text
    assert client.get(f"/api/v1/channels/{parent_id}/items").json()["items"] == []
    pending = client.get("/api/v1/admin/pushes", headers=headers(boss)).json()
    assert [row["content_id"] for row in pending["items"]] == [content_id]
    assert (pending["items"][0]["room_name"], pending["items"][0]["channel_name"]) == ("空房间", "英国租房")
    assert client.get("/api/v1/admin/stats", headers=headers(boss)).json()["pending_pushes"] == 1  # 菜单「待审核」的数字要算上推送
    approve_push(client, boss, content_id)
    assert client.get("/api/v1/admin/pushes", headers=headers(boss)).json()["items"] == []
    again = client.post(f"/api/v1/admin/pushes/{content_id}/decision", headers=headers(boss), json={"decision": "reject"})
    assert again.status_code == 409  # 处理过的不能再改
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
    approve_push(client, admin_for(client), content_id)
    assert content_id in [item["content_id"] for item in client.get(f"/api/v1/channels/{parent_id}/items").json()["items"]]
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


def test_owner_can_fill_rename_and_show_a_pending_room(client):
    """新建的房间在审核中：房主能改名、能先加条目（待审，不外漏），主页本人可见、别人不可见；审核通过一条后上线。"""
    from app.models import BlockedTerm

    owner = register(client, "pending-owner@example.com")
    verify(client, owner, "+447700900311")
    stranger = register(client, "pending-stranger@example.com")
    parent_id = official_channel(client)
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "待审剧", "parent_channel_id": parent_id, "room_type": "series"}
    ).json()["channel_id"]
    with client.session_factory() as session:
        owner_id = session.scalar(select(User.id).where(User.email == "pending-owner@example.com"))
        session.add(BlockedTerm(term="坏词"))
        session.commit()

    # 改名、改类型；敏感词房名被挡
    renamed = client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"name": "伦敦剧场"})
    assert renamed.status_code == 200 and renamed.json()["name_hans"] == "伦敦剧场"
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"name": "坏词房"}).status_code == 422
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(stranger), json={"name": "抢房"}).status_code == 404
    # 新建时也挡：房间第一条帖子直接公开时会跟着上线，名字可能没人看过
    created_bad = client.post("/api/v1/channels", headers=headers(owner), json={"name": "坏词房", "parent_channel_id": parent_id})
    assert created_bad.status_code == 422

    # 审核中也能加条目，但先待审：房主自己能看到，搜索 / 主页里没有
    entry = client.post(
        f"/api/v1/channels/{room_id}/entries",
        headers=headers(owner),
        json={"title": "第一集", "body": "内容", "season": 1, "episode": 1},
    )
    assert entry.status_code == 200, entry.text
    assert entry.json()["status"] == "pending"
    assert [row["title"] for row in client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()["items"]] == ["第一集"]
    assert client.get(f"/api/v1/users/{owner_id}/posts").json()["items"] == []

    # 主页：本人看到审核中的房间，别人看不到
    mine = client.get(f"/api/v1/users/{owner_id}", headers=headers(owner)).json()["rooms"]
    assert [(room["name_hans"], room["pending"]) for room in mine] == [("伦敦剧场", True)]
    assert client.get(f"/api/v1/users/{owner_id}", headers=headers(stranger)).json()["rooms"] == []

    # 条目审核通过 → 房间自动上线，别人也能在主页看到
    approved = client.post(f"/api/v1/moderation/{entry.json()['content_id']}/decision", headers=headers(owner), json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    shown = client.get(f"/api/v1/users/{owner_id}").json()["rooms"]
    assert [(room["name_hans"], room["pending"]) for room in shown] == [("伦敦剧场", False)]

    # 房间上线后，帖子直接发布，不进后台审核
    clean = client.post("/api/v1/contents", headers=headers(owner), json={"channel_id": room_id, "title": "房主帖", "body": "正文"})
    assert clean.json()["status"] == "published"
    # 命中敏感词的等平台审核：不进房间的待审队列，也不能在房间里自己通过
    own = client.post("/api/v1/contents", headers=headers(owner), json={"channel_id": room_id, "title": "房主帖", "body": "正文 坏词"})
    assert own.status_code == 200, own.text
    assert own.json()["status"] == "pending"
    assert client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(owner)).json()["items"] == []
    self_ok = client.post(
        f"/api/v1/channels/{room_id}/submissions/{own.json()['content_id']}/decision",
        headers=headers(owner),
        json={"decision": "accept"},
    )
    assert self_ok.status_code == 403


def test_my_rooms_lists_rooms_i_can_post_to(client):
    """发布页「我的房间」：自己建的、自己协作的综合讨论房间；别人的、非综合类、被拒的不列。"""
    owner = register(client, "mine-owner@example.com")
    other = register(client, "mine-other@example.com")
    verify(client, owner, "+447700900321")
    verify(client, other, "+447700900322")
    parent_id = official_channel(client)

    def create(token: str, name: str, room_type: str = "general") -> str:
        return client.post(
            "/api/v1/channels", headers=headers(token), json={"name": name, "parent_channel_id": parent_id, "room_type": room_type}
        ).json()["channel_id"]

    mine = create(owner, "我的综合")
    series = create(owner, "我的剧集", "series")
    rejected = create(owner, "被拒房")
    shared = create(other, "别人的房")
    others_only = create(other, "别人自己的")
    with client.session_factory() as session:
        owner_id = session.scalar(select(User.id).where(User.email == "mine-owner@example.com"))
        session.get(Channel, rejected).review_status = "rejected"
        session.commit()
    assert client.put(f"/api/v1/channels/{shared}/collaborators/{owner_id}", headers=headers(other)).status_code == 200

    ids = [item["id"] for item in client.get("/api/v1/channels/mine", headers=headers(owner)).json()["items"]]
    assert set(ids) == {mine, series, shared}
    assert others_only not in ids
    assert client.get("/api/v1/channels/mine").status_code == 401


def test_entries_and_room_posts_take_video_links(client):
    """电影 / 视频 / 剧集条目和综合讨论帖子都能用视频外链；外链和上传二选一，白名单外的平台拒绝。"""
    owner = register(client, "link-owner@example.com")
    verify(client, owner, "+447700900215")
    parent_id = official_channel(client)

    def room(name: str, room_type: str) -> str:
        room_id = client.post(
            "/api/v1/channels", headers=headers(owner), json={"name": name, "parent_channel_id": parent_id, "room_type": room_type}
        ).json()["channel_id"]
        assert client.post(
            f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"}
        ).status_code == 200
        return room_id

    def entry(room_id: str, **extra):
        return client.post(f"/api/v1/channels/{room_id}/entries", headers=headers(owner), json={"title": "预告", "body": "看看", **extra})

    film = room("外链片单", "film")
    added = entry(film, video_url="https://www.bilibili.com/video/BV1GJ411x7h7?p=1")
    assert added.status_code == 200, added.text
    row = client.get(f"/api/v1/channels/{film}/items").json()["items"][0]
    assert row["type"] == "embed" and row["embed_status"] == "embeddable"
    assert row["canonical_url"] == "https://www.bilibili.com/video/BV1GJ411x7h7"
    consent = client.get(f"/api/v1/embed/{added.json()['content_id']}/consent", headers=headers(owner)).json()
    assert consent["provider_code"] == "bilibili"

    clip = upload(client, owner, "video/mp4", b"\x00\x00\x00\x18ftyp")
    both = entry(film, video_key=clip, video_url="https://www.youtube.com/watch?v=abcdefghijk")
    assert both.status_code == 400
    assert entry(film, video_url="https://vimeo.com/123").json()["code"] == "EMBED_PROVIDER_NOT_ALLOWED"

    # 视频房间：外链不是本人原创，不用勾原创确认
    video = room("外链视频", "video")
    assert entry(video, video_url="https://www.youtube.com/watch?v=abcdefghijk").status_code == 200
    series = room("外链剧集", "series")
    assert entry(series, season=1, episode=1, video_url="https://www.youtube.com/watch?v=abcdefghijk").status_code == 200

    general = room("外链讨论", "general")
    posted = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": general, "title": "推荐一个视频", "body": "大家看看", "video_url": "https://www.youtube.com/watch?v=abcdefghijk"},
    )
    assert posted.status_code == 200, posted.text
    session = client.session_factory()
    saved = session.get(Content, posted.json()["content_id"])
    assert saved.type == "embed" and saved.embed_provider_code == "youtube"
    session.close()
    mixed = client.post(
        "/api/v1/contents",
        headers=headers(owner),
        json={"channel_id": general, "title": "两个都填", "body": "x", "post_type": "video", "rights_confirmed": True, "video_key": clip, "video_url": "https://www.youtube.com/watch?v=abcdefghijk"},
    )
    assert mixed.status_code == 400


def test_banned_member_cannot_post_or_comment_in_public_room(client):
    """公开房间不加入也能发：被移出的人发帖、房间留言、帖子下回复都要拦住。"""
    parent_id = official_channel(client)
    owner = register(client, "pub-ban-owner@example.com")
    verify(client, owner, "+447700900351")
    member = register(client, "pub-ban-member@example.com")
    verify(client, member, "+447700900352")
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "公开房间", "parent_channel_id": parent_id}).json()[
        "channel_id"
    ]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    base = f"/api/v1/channels/{room_id}"
    post = client.post(f"{base}/announcements", headers=headers(owner), json={"title": "公告", "body": "欢迎"}).json()
    assert post["status"] == "published"
    member_id = client.get("/api/v1/me", headers=headers(member)).json()["user_id"]
    assert client.put(f"{base}/bans/{member_id}", headers=headers(owner)).status_code == 200

    attempts = [
        client.post("/api/v1/contents", headers=headers(member), json={"channel_id": room_id, "title": "还想发", "body": "被移出了还发"}),
        client.post(f"{base}/comments", headers=headers(member), json={"body": "还想留言"}),
        client.post(f"/api/v1/contents/{post['content_id']}/comments", headers=headers(member), json={"body": "还想回复"}),
        client.post(f"{base}/submissions", headers=headers(member), json={"title": "投稿", "body": "还想投稿"}),
    ]
    assert [(r.status_code, r.json()["code"]) for r in attempts] == [(403, "ROOM_BANNED")] * 4


def test_blocked_user_cannot_reply_under_the_blockers_posts(client):
    """拉黑不只挡私信：被拉黑的人不能在对方的帖子下回复（两个回复入口都挡），别人照常。"""
    parent_id = official_channel(client)
    owner = register(client, "block-owner@example.com")
    verify(client, owner, "+447700900361")
    pest = register(client, "block-pest@example.com")
    friend = register(client, "block-friend@example.com")
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "拉黑测试", "parent_channel_id": parent_id}).json()[
        "channel_id"
    ]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    content_id = client.post(
        f"/api/v1/channels/{room_id}/announcements", headers=headers(owner), json={"title": "公告", "body": "欢迎"}
    ).json()["content_id"]
    pest_id = client.get("/api/v1/me", headers=headers(pest)).json()["user_id"]
    assert client.put(f"/api/v1/me/blocks/{pest_id}", headers=headers(owner)).status_code == 200

    reply = client.post(f"/api/v1/contents/{content_id}/comments", headers=headers(pest), json={"body": "还来"})
    room_reply = client.post(f"/api/v1/channels/{room_id}/comments", headers=headers(pest), json={"body": "还来", "content_id": content_id})
    assert [(r.status_code, r.json()["code"]) for r in (reply, room_reply)] == [(403, "USER_BLOCKED")] * 2
    assert client.post(f"/api/v1/contents/{content_id}/comments", headers=headers(friend), json={"body": "你好"}).status_code == 200


def test_owner_bans_a_member_and_deletes_the_room(client):
    parent_id = official_channel(client)
    owner = register(client, "ban-owner@example.com")
    verify(client, owner, "+447700900341")
    member = register(client, "ban-member@example.com")
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "只给熟人", "parent_channel_id": parent_id, "is_private": True}
    ).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    base = f"/api/v1/channels/{room_id}"
    request_id = client.post(f"{base}/join-requests", headers=headers(member)).json()["request_id"]
    assert client.post(f"{base}/join-requests/{request_id}/approve", headers=headers(owner)).status_code == 200
    assert client.get(f"{base}/items", headers=headers(member)).status_code == 200

    # 只有房主能看成员、移出成员
    assert client.get(f"{base}/members", headers=headers(member)).status_code == 403
    members = client.get(f"{base}/members", headers=headers(owner)).json()
    assert len(members["items"]) == 1 and members["banned"] == []
    member_id = members["items"][0]["user_id"]
    assert client.put(f"{base}/bans/{member_id}", headers=headers(member)).status_code == 403
    assert client.put(f"{base}/bans/{member_id}", headers=headers(owner)).status_code == 200

    # 移出后看不到内容，也不能再申请
    assert client.get(f"{base}/items", headers=headers(member)).status_code == 404
    again = client.post(f"{base}/join-requests", headers=headers(member))
    assert again.status_code == 403 and again.json()["code"] == "ROOM_BANNED"
    members = client.get(f"{base}/members", headers=headers(owner)).json()
    assert members["items"] == [] and members["banned"][0]["user_id"] == member_id
    assert client.get(base, headers=headers(owner)).json()["subscriber_count"] == 0

    # 解除后可以重新申请
    assert client.delete(f"{base}/bans/{member_id}", headers=headers(owner)).status_code == 200
    assert client.post(f"{base}/join-requests", headers=headers(member)).status_code == 200

    # 删除房间：别人删不了；房主删掉后房间没了，只属于它的帖子下架
    content_id = client.post(f"{base}/announcements", headers=headers(owner), json={"title": "公告", "body": "大家好"}).json()["content_id"]
    assert client.delete(base, headers=headers(member)).status_code == 404
    deleted = client.delete(base, headers=headers(owner))
    assert deleted.status_code == 200 and deleted.json()["removed_posts"] == 1
    assert client.get(base, headers=headers(owner)).status_code == 404
    with client.session_factory() as session:
        from app.models import RoomJoinRequest

        assert session.get(Channel, room_id) is None
        assert session.get(Content, content_id).status == "deleted"
        assert session.scalar(select(RoomJoinRequest).where(RoomJoinRequest.room_id == room_id)) is None


def test_owner_posts_in_own_room_follow_banned_words_and_hourly_cap(client):
    """房主发公告、放行投稿，和普通发帖同一套规则：敏感词先待审 / 不能放行，每小时最多 5 条。"""
    from app.models import BlockedTerm

    parent_id = official_channel(client)
    owner = register(client, "gate-owner@example.com")
    verify(client, owner, "+447700900371")
    member = register(client, "gate-member@example.com")
    verify(client, member, "+447700900372")
    with client.session_factory() as session:
        session.add(BlockedTerm(term="坏词"))
        session.commit()
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "规则房间", "parent_channel_id": parent_id}).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    base = f"/api/v1/channels/{room_id}"

    held = client.post(f"{base}/announcements", headers=headers(owner), json={"title": "坏词公告", "body": "内容"}).json()
    assert held["status"] == "pending"
    guest_ids = [item["content_id"] for item in client.get(f"{base}/items").json()["items"]]
    assert held["content_id"] not in guest_ids

    submitted = client.post(f"{base}/submissions", headers=headers(member), json={"title": "投稿", "body": "带坏词的投稿"}).json()
    accept = client.post(f"{base}/submissions/{submitted['content_id']}/decision", headers=headers(owner), json={"decision": "accept"})
    assert (accept.status_code, accept.json()["code"]) == (422, "BLOCKED_TERM")

    for index in range(4):  # 加上上面那条，正好 5 条
        assert client.post(f"{base}/announcements", headers=headers(owner), json={"title": f"公告{index}", "body": "内容"}).status_code == 200
    over = client.post(f"{base}/announcements", headers=headers(owner), json={"title": "第六条", "body": "内容"})
    assert (over.status_code, over.json()["code"]) == (429, "RATE_LIMITED")


def test_taken_down_room_hides_its_posts_and_owner_cannot_post_on(client):
    """举报后下架房间：房间里的帖子在搜索、主页、按链接、官方频道（推送的副本）都看不到，只有房主还能看；房主也不能再往里发帖。"""
    parent_id = official_channel(client)
    owner = register(client, "down-owner@example.com")
    verify(client, owner, "+447700900381")
    viewer = register(client, "down-viewer@example.com")
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "要下架的房间", "parent_channel_id": parent_id}).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    content_id = client.post(
        f"/api/v1/channels/{room_id}/announcements", headers=headers(owner), json={"title": "下架测试公告", "body": "内容"}
    ).json()["content_id"]
    assert client.post(f"/api/v1/channels/{room_id}/pushes/{content_id}", headers=headers(owner)).status_code == 200
    approve_push(client, admin_for(client), content_id)
    owner_id = client.get("/api/v1/me", headers=headers(owner)).json()["user_id"]

    def visible() -> list[bool]:
        return [
            content_id in {item["content_id"] for item in client.get("/api/v1/search", params={"q": "下架测试公告"}).json()["contents"]},
            content_id in {item["content_id"] for item in client.get(f"/api/v1/users/{owner_id}/posts").json()["items"]},
            content_id in {item["content_id"] for item in client.get(f"/api/v1/channels/{parent_id}/items").json()["items"]},
            client.get(f"/api/v1/contents/{content_id}").status_code == 200,
        ]

    assert visible() == [True] * 4
    case_id = client.post(f"/api/v1/channels/{room_id}/report", headers=headers(viewer), json={"reason": "scam"}).json()["case_id"]
    removed = client.post(f"/api/v1/moderation/cases/{case_id}/decision", headers=headers(viewer), json={"decision": "remove"})
    assert removed.status_code == 200, removed.text

    assert visible() == [False] * 4
    assert client.get(f"/api/v1/contents/{content_id}", headers=headers(owner)).status_code == 200
    again = client.post("/api/v1/contents", headers=headers(owner), json={"channel_id": room_id, "title": "接着发", "body": "下架了还发"})
    assert (again.status_code, again.json()["code"]) == (404, "CHANNEL_NOT_FOUND")


def test_erased_account_no_longer_counts_as_follower(client):
    star = register(client, "follow-star@example.com")
    fan = register(client, "follow-fan@example.com")
    star_id = client.get("/api/v1/me", headers=headers(star)).json()["user_id"]
    assert client.put(f"/api/v1/me/follows/{star_id}", headers=headers(fan)).status_code == 200
    assert client.get(f"/api/v1/users/{star_id}").json()["follower_count"] == 1
    assert client.delete("/api/v1/me", headers=headers(fan)).status_code == 200
    assert client.get(f"/api/v1/users/{star_id}").json()["follower_count"] == 0


def test_push_to_any_channel_is_reviewed_and_rejected_can_be_retried(client):
    """房间不属于任何频道：房主可以把帖子推到任意官方频道，后台审核；被拒的可以再推；房间位可以撤掉。"""
    channel_id = official_channel(client)
    owner = register(client, "free-owner@example.com")
    verify(client, owner, "+447700900391")
    boss = admin_for(client)
    room_id = client.post("/api/v1/channels", headers=headers(owner), json={"name": "自由房间"}).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    content_id = client.post(
        f"/api/v1/channels/{room_id}/announcements", headers=headers(owner), json={"title": "想上频道", "body": "内容"}
    ).json()["content_id"]
    base = f"/api/v1/channels/{room_id}/pushes/{content_id}"

    assert client.post(base, headers=headers(owner)).json()["code"] == "CHANNEL_REQUIRED"  # 没有父频道又没选频道
    assert client.post(base, headers=headers(owner), json={"channel_id": room_id}).status_code == 404  # 只能推官方频道
    assert client.post(base, headers=headers(owner), json={"channel_id": channel_id}).json()["status"] == "pending"

    # 房主在自己房间的条目上看得到推送状态，别人看不到
    mine = client.get(f"/api/v1/channels/{room_id}/items", headers=headers(owner)).json()["items"][0]
    assert (mine["push_status"], mine["push_channel_name"]) == ("pending", "英国租房")
    assert client.get(f"/api/v1/channels/{room_id}/items").json()["items"][0]["push_status"] is None

    rejected = client.post(f"/api/v1/admin/pushes/{content_id}/decision", headers=headers(boss), json={"decision": "reject", "reason": "不合适"})
    assert rejected.status_code == 200
    assert client.get(f"/api/v1/channels/{channel_id}/items").json()["items"] == []
    assert client.post(base, headers=headers(owner), json={"channel_id": channel_id}).json()["status"] == "pending"  # 被拒后可再推
    approve_push(client, boss, content_id)
    assert [item["content_id"] for item in client.get(f"/api/v1/channels/{channel_id}/items").json()["items"]] == [content_id]

    assert set_slot(client, boss, channel_id, room_id).status_code == 200
    assert [row["room_id"] for row in client.get(f"/api/v1/admin/channels/{channel_id}/slots", headers=headers(boss)).json()["items"]] == [room_id]
    assert client.post(f"/api/v1/admin/channels/{channel_id}/slots/{room_id}/delete", headers=headers(boss), json={}).status_code == 200
    assert client.get(f"/api/v1/channels/{channel_id}").json()["rooms"] == []


def test_series_episodes_need_no_season_or_body_and_can_be_added_in_bulk(client):
    """剧集只填集号就行（不分季、正文可不写），一次加十来集不会被每小时 5 条的发帖限制拦住。"""
    owner = register(client, "bulk-owner@example.com")
    verify(client, owner, "+447700900392")
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "追更剧", "room_type": "series"}
    ).json()["channel_id"]
    client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    url = f"/api/v1/channels/{room_id}/entries"

    for number in range(1, 13):
        added = client.post(url, headers=headers(owner), json={"title": f"第 {number} 集", "episode": number})
        assert added.status_code == 200, added.text
        assert added.json()["sort_key"] == f"S01E{number:03d}"
    assert client.post(url, headers=headers(owner), json={"title": "重复", "episode": 3}).json()["code"] == "EPISODE_TAKEN"
    assert client.post(url, headers=headers(owner), json={"title": "没集号"}).status_code == 400

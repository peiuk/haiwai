"""房间内容房主自己管：房主 / 协作者直接发、成员的帖子等房主通过、房主能删、作者能改、后台精选的房间帖进推荐和发现。"""
from app.models import BlockedTerm, Content, utcnow
from tests.test_rooms import headers, official_channel, register, verify


def _live_room(client, owner: str, name: str = "自管房间", private: bool = False, parent_id: str | None = None) -> str:
    room_id = client.post(
        "/api/v1/channels",
        headers=headers(owner),
        json={"name": name, "parent_channel_id": parent_id or official_channel(client), "is_private": private},
    ).json()["channel_id"]
    approved = client.post(f"/api/v1/moderation/channels/{room_id}/decision", headers=headers(owner), json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    return room_id


def _post(client, token: str, room_id: str, title: str = "帖子", body: str = "第一次发帖") -> dict:
    posted = client.post("/api/v1/contents", headers=headers(token), json={"channel_id": room_id, "title": title, "body": body})
    assert posted.status_code == 200, posted.text
    return posted.json()


def _accepted_member_post(client, owner: str, member: str, room_id: str) -> str:
    """成员直接调发帖接口也只算投稿：先待审，房主通过后才公开。"""
    post = _post(client, member, room_id, "成员的帖子")
    assert post["status"] == "pending"
    accepted = client.post(
        f"/api/v1/channels/{room_id}/submissions/{post['content_id']}/decision", headers=headers(owner), json={"decision": "accept"}
    )
    assert accepted.status_code == 200, accepted.text
    return post["content_id"]


def _pending_ids(client, admin: str) -> set[str]:
    return {item["content_id"] for item in client.get("/api/v1/admin/queue", headers=headers(admin)).json()["contents"]}


def test_member_posts_wait_for_the_owner_not_the_admin(client):
    owner = register(client, "manage-owner@example.com")
    verify(client, owner, "+447700900601")
    member = register(client, "manage-member@example.com")
    verify(client, member, "+447700900602")
    stranger = register(client, "manage-stranger@example.com")
    room_id = _live_room(client, owner)

    # 房主自己发的直接公开（新用户也不进后台审核）
    assert _post(client, owner, room_id, "房主的帖子")["status"] == "published"

    post = _post(client, member, room_id, "成员的帖子")
    assert post["status"] == "pending"
    waiting = client.get(f"/api/v1/channels/{room_id}/submissions", headers=headers(owner)).json()["items"]
    assert [item["content_id"] for item in waiting] == [post["content_id"]]
    assert client.get(f"/api/v1/contents/{post['content_id']}", headers=headers(stranger)).status_code == 404

    content_id = _accepted_member_post(client, owner, member, room_id)
    seen_by_owner = client.get(f"/api/v1/contents/{content_id}", headers=headers(owner)).json()
    assert (seen_by_owner["can_edit"], seen_by_owner["can_delete"]) == (False, True)
    seen_by_stranger = client.get(f"/api/v1/contents/{content_id}", headers=headers(stranger)).json()
    assert (seen_by_stranger["can_edit"], seen_by_stranger["can_delete"]) == (False, False)

    assert client.delete(f"/api/v1/contents/{content_id}", headers=headers(stranger)).status_code == 403
    removed = client.delete(f"/api/v1/contents/{content_id}", headers=headers(owner))
    assert removed.status_code == 200, removed.text
    assert client.get(f"/api/v1/contents/{content_id}", headers=headers(member)).status_code == 404


def test_only_the_author_edits_and_the_edit_is_reviewed_again(client):
    owner = register(client, "edit-owner@example.com")
    verify(client, owner, "+447700900611")
    member = register(client, "edit-member@example.com")
    verify(client, member, "+447700900612")
    room_id = _live_room(client, owner)
    content_id = _accepted_member_post(client, owner, member, room_id)
    url = f"/api/v1/contents/{content_id}"

    # 房主不能改别人的帖子（管不了就删），游客更不行
    assert client.patch(url, headers=headers(owner), json={"title": "房主改的", "body": "替别人说话"}).status_code == 403
    assert client.patch(url, json={"title": "游客", "body": "游客"}).status_code == 401
    assert client.patch(url, headers=headers(member), json={"title": " ", "body": "空标题"}).status_code == 422

    # 成员改完回到房主那里：审的和公开的要是同一个版本
    edited = client.patch(url, headers=headers(member), json={"title": "改过的标题", "body": "改过的正文 #新话题"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "pending"
    assert client.get(url, headers=headers(owner)).status_code == 404  # 待审：别人看不到
    shown = client.get(url, headers=headers(member)).json()  # 作者自己还能看、能再改
    assert (shown["title"], shown["body"], shown["keywords"], shown["can_edit"]) == ("改过的标题", "改过的正文 #新话题", ["新话题"], True)

    # 房主改自己的帖子不用再审；命中敏感词的照样拦，而且是后台来审
    own = _post(client, owner, room_id, "房主的帖子")["content_id"]
    own_url = f"/api/v1/contents/{own}"
    with client.session_factory() as session:
        session.get(Content, own).featured_at = utcnow()
        session.commit()
    assert client.patch(own_url, headers=headers(owner), json={"title": "房主改过", "body": "正常内容"}).json()["status"] == "published"
    with client.session_factory() as session:
        assert session.get(Content, own).featured_at is None  # 精选的是改之前的版本
        session.add(BlockedTerm(term="casino"))
        session.commit()
    assert client.patch(own_url, headers=headers(owner), json={"title": "房主改过", "body": "来 Casino 玩"}).json()["status"] == "pending"


def test_featured_room_post_reaches_for_you_and_discover(client):
    owner = register(client, "featured-owner@example.com")
    verify(client, owner, "+447700900621")
    parent_id = official_channel(client)
    public_post = _post(client, owner, _live_room(client, owner, parent_id=parent_id), "公开房间的帖子")["content_id"]
    private_post = _post(client, owner, _live_room(client, owner, "私密房间", True, parent_id), "私密房间的帖子")["content_id"]
    uk = {"X-Region": "UK"}

    def shown() -> tuple[set[str], set[str]]:
        for_you = {item["content_id"] for item in client.get("/api/v1/me/feed?tab=foryou", headers=uk).json()["items"]}
        discover = {item["content_id"] for item in client.get("/api/v1/discover/items", headers=uk).json()["items"]}
        return for_you, discover

    for_you, discover = shown()
    assert public_post not in for_you | discover  # 没精选：房间帖不进推荐和发现

    with client.session_factory() as session:
        for content_id in (public_post, private_post):
            session.get(Content, content_id).featured_at = utcnow()
        session.commit()
    for_you, discover = shown()
    assert public_post in for_you and public_post in discover
    assert private_post not in for_you | discover  # 私密房间的帖子精选了也不外露

"""房间内容房主自己管：成员帖子不进后台审核、房主能删、作者能改、后台精选的房间帖进推荐和发现。"""
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


def _member_post(client, member: str, room_id: str, title: str = "成员的帖子", body: str = "第一次发帖") -> str:
    posted = client.post("/api/v1/contents", headers=headers(member), json={"channel_id": room_id, "title": title, "body": body})
    assert posted.status_code == 200, posted.text
    # 新用户的前几条本来要后台审；已上线房间里的帖子不用
    assert posted.json()["status"] == "published"
    return posted.json()["content_id"]


def test_room_owner_deletes_a_members_post_but_strangers_cannot(client):
    owner = register(client, "manage-owner@example.com")
    verify(client, owner, "+447700900601")
    member = register(client, "manage-member@example.com")
    verify(client, member, "+447700900602")
    stranger = register(client, "manage-stranger@example.com")
    content_id = _member_post(client, member, _live_room(client, owner))

    seen_by_owner = client.get(f"/api/v1/contents/{content_id}", headers=headers(owner)).json()
    assert (seen_by_owner["can_edit"], seen_by_owner["can_delete"]) == (False, True)
    seen_by_stranger = client.get(f"/api/v1/contents/{content_id}", headers=headers(stranger)).json()
    assert (seen_by_stranger["can_edit"], seen_by_stranger["can_delete"]) == (False, False)

    assert client.delete(f"/api/v1/contents/{content_id}", headers=headers(stranger)).status_code == 403
    removed = client.delete(f"/api/v1/contents/{content_id}", headers=headers(owner))
    assert removed.status_code == 200, removed.text
    assert client.get(f"/api/v1/contents/{content_id}", headers=headers(member)).status_code == 404


def test_only_the_author_edits_and_banned_words_send_it_back_to_review(client):
    owner = register(client, "edit-owner@example.com")
    verify(client, owner, "+447700900611")
    member = register(client, "edit-member@example.com")
    verify(client, member, "+447700900612")
    content_id = _member_post(client, member, _live_room(client, owner))
    url = f"/api/v1/contents/{content_id}"

    # 房主不能改别人的帖子（管不了就删），游客更不行
    assert client.patch(url, headers=headers(owner), json={"title": "房主改的", "body": "替别人说话"}).status_code == 403
    assert client.patch(url, json={"title": "游客", "body": "游客"}).status_code == 401

    edited = client.patch(url, headers=headers(member), json={"title": "改过的标题", "body": "改过的正文 #新话题"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "published"
    shown = client.get(url, headers=headers(member)).json()
    assert (shown["title"], shown["body"], shown["keywords"]) == ("改过的标题", "改过的正文 #新话题", ["新话题"])
    assert shown["can_edit"] is True

    assert client.patch(url, headers=headers(member), json={"title": " ", "body": "空标题"}).status_code == 422

    with client.session_factory() as session:
        session.add(BlockedTerm(term="casino"))
        session.commit()
    hidden = client.patch(url, headers=headers(member), json={"title": "改过的标题", "body": "来 Casino 玩"})
    assert hidden.json()["status"] == "pending"
    assert client.get(url, headers=headers(owner)).status_code == 404  # 待审：别人看不到
    assert client.get(url, headers=headers(member)).status_code == 200  # 作者自己还能看、能再改


def test_featured_room_post_reaches_for_you_and_discover(client):
    owner = register(client, "featured-owner@example.com")
    verify(client, owner, "+447700900621")
    parent_id = official_channel(client)
    public_post = _member_post(client, owner, _live_room(client, owner, parent_id=parent_id), title="公开房间的帖子")
    private_post = _member_post(client, owner, _live_room(client, owner, "私密房间", True, parent_id), title="私密房间的帖子")
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

"""关注的人发到「我的动态」的帖子（不在任何频道里）进关注流；搜索结果带「是否已关注发帖人」。"""
from sqlalchemy import select

from app.models import Content, User, UserBlock, utcnow
from tests.test_h5_domain import headers, register


def _user_id(client, email: str) -> str:
    session = client.session_factory()
    try:
        return session.scalar(select(User.id).where(User.email == email))
    finally:
        session.close()


def _moment(client, author_id: str, title: str, status: str = "published") -> str:
    session = client.session_factory()
    content = Content(
        type="post",
        status=status,
        author_id=author_id,
        title=title,
        summary=title,
        body=title,
        source_name="作者",
        published_at=utcnow() if status == "published" else None,
    )
    session.add(content)
    session.commit()
    content_id = content.id
    session.close()
    return content_id


def _feed_ids(client, token: str) -> list[str]:
    response = client.get("/api/v1/me/feed", headers=headers(token))
    assert response.status_code == 200, response.text
    return [item["content_id"] for item in response.json()["items"]]


def test_followed_users_moments_show_in_following_feed(client):
    register(client, "moment-author@example.com", "作者")
    reader = register(client, "moment-reader@example.com", "读者")
    author_id = _user_id(client, "moment-author@example.com")
    reader_id = _user_id(client, "moment-reader@example.com")
    shown = _moment(client, author_id, "周末去海边")
    pending = _moment(client, author_id, "还在审核", status="pending")

    assert shown not in _feed_ids(client, reader)  # 没关注：不进关注流

    assert client.put(f"/api/v1/me/follows/{author_id}", headers=headers(reader)).status_code == 200
    items = client.get("/api/v1/me/feed", headers=headers(reader)).json()["items"]
    card = next(item for item in items if item["content_id"] == shown)
    assert card["channel_id"] == "" and card["author_id"] == author_id and card["author_name"] == "作者"
    assert pending not in [item["content_id"] for item in items]  # 待审的不出现

    # 拉黑后不再出现（即使关注关系还在）
    session = client.session_factory()
    session.add(UserBlock(user_id=reader_id, target_id=author_id))
    session.commit()
    session.close()
    assert shown not in _feed_ids(client, reader)
    session = client.session_factory()
    session.delete(session.get(UserBlock, (reader_id, author_id)))
    session.commit()
    session.close()

    assert client.delete(f"/api/v1/me/follows/{author_id}", headers=headers(reader)).status_code == 200
    assert shown not in _feed_ids(client, reader)  # 取消关注后消失


def test_search_marks_whether_viewer_follows_the_author(client):
    register(client, "searched-author@example.com", "作者")
    reader = register(client, "searcher@example.com", "读者")
    author_id = _user_id(client, "searched-author@example.com")
    _moment(client, author_id, "独一无二的海鸥")

    def following() -> bool:
        body = client.get("/api/v1/search", params={"q": "独一无二的海鸥"}, headers=headers(reader)).json()
        return body["contents"][0]["author_following"]

    assert following() is False
    client.put(f"/api/v1/me/follows/{author_id}", headers=headers(reader))
    assert following() is True

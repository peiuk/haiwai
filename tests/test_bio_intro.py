"""个人介绍和房间介绍：本人 / 房主能写、能清空，主页和房间页带出，敏感词和超长被挡，注销时抹掉。"""

from sqlalchemy import select

from app.models import BlockedTerm, User
from tests.test_rooms import headers, official_channel, register, verify


def test_user_bio_set_shown_validated_and_erased(client):
    token = register(client, "bio-user@example.com")
    with client.session_factory() as session:
        session.add(BlockedTerm(term="坏词"))
        session.commit()
        user_id = session.scalar(select(User.id).where(User.email == "bio-user@example.com"))

    saved = client.patch("/api/v1/me", headers=headers(token), json={"bio": "  伦敦码农，周末爬山  "})
    assert saved.status_code == 200 and saved.json()["bio"] == "伦敦码农，周末爬山"
    assert client.get(f"/api/v1/users/{user_id}").json()["bio"] == "伦敦码农，周末爬山"

    assert client.patch("/api/v1/me", headers=headers(token), json={"bio": "x" * 251}).status_code == 422
    assert client.patch("/api/v1/me", headers=headers(token), json={"bio": "我是坏词"}).status_code == 422
    # 只改别的字段不动介绍；传空字符串清空
    assert client.patch("/api/v1/me", headers=headers(token), json={"city_label": "London"}).json()["bio"] == "伦敦码农，周末爬山"
    assert client.patch("/api/v1/me", headers=headers(token), json={"bio": ""}).json()["bio"] == ""

    client.patch("/api/v1/me", headers=headers(token), json={"bio": "要被抹掉"})
    assert client.delete("/api/v1/me", headers=headers(token)).status_code == 200
    with client.session_factory() as session:
        assert session.get(User, user_id).bio is None


def test_room_intro_owner_only(client):
    owner = register(client, "intro-owner@example.com")
    verify(client, owner, "+447700900231")
    other = register(client, "intro-other@example.com")
    room_id = client.post(
        "/api/v1/channels", headers=headers(owner), json={"name": "伦敦徒步", "parent_channel_id": official_channel(client)}
    ).json()["channel_id"]

    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(other), json={"intro": "抢房"}).status_code in (403, 404)
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"intro": "每周六一起走"}).status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}", headers=headers(owner)).json()["intro"] == "每周六一起走"
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"intro": "x" * 251}).status_code == 422
    assert client.patch(f"/api/v1/channels/{room_id}", headers=headers(owner), json={"intro": ""}).status_code == 200
    assert client.get(f"/api/v1/channels/{room_id}", headers=headers(owner)).json()["intro"] == ""

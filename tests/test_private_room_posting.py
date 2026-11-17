"""房主和成员能在私密房间里发帖。"""
from tests.test_private_room_access import auth, private_room


def test_owner_can_publish_to_private_room(client):
    room_id, owner, _ = private_room(client)
    posted = client.post("/api/v1/contents", headers=auth(owner), json={"channel_id": room_id, "title": "房主的帖子", "body": "只给成员看"})
    assert posted.status_code == 200, posted.text
    content_id = posted.json()["content_id"]
    assert posted.json()["status"] == "published"  # 已上线房间里的帖子不进后台审核
    detail = client.get(f"/api/v1/contents/{content_id}", headers=auth(owner))
    assert detail.status_code == 200, detail.text
    room = client.get(f"/api/v1/channels/{room_id}", headers=auth(owner))
    assert room.status_code == 200, room.text
    print(room.json().keys())

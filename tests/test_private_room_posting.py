"""房主和成员能在私密房间里发帖。"""
from tests.test_private_room_access import auth, private_room


def test_owner_can_publish_to_private_room(client):
    room_id, owner, _ = private_room(client)
    posted = client.post("/api/v1/contents", headers=auth(owner), json={"channel_id": room_id, "title": "房主的帖子", "body": "只给成员看"})
    assert posted.status_code == 200, posted.text
    content_id = posted.json()["content_id"]
    approved = client.post(f"/api/v1/moderation/{content_id}/decision", headers=auth(owner), json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/api/v1/contents/{content_id}", headers=auth(owner))
    assert detail.status_code == 200, detail.text
    room = client.get(f"/api/v1/channels/{room_id}", headers=auth(owner))
    assert room.status_code == 200, room.text
    print(room.json().keys())

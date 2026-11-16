"""后台流程里发现的问题：注销用户的待审房间不该一直留在队列；操作日志的「对象」要能看出是谁 / 哪条。"""
from app.models import Channel
from tests.test_admin import headers, register, user_id
from tests.test_rooms import official_channel, verify


def test_deleted_owner_room_leaves_review_queue(client):
    admin = register(client, "queue-admin@example.com", admin=True)
    owner = register(client, "leaving-owner@example.com")
    verify(client, owner, "+447700900901")
    parent = official_channel(client)
    created = client.post("/api/v1/channels", headers=headers(owner), json={"name": "要走的人的房间", "parent_channel_id": parent})
    assert created.status_code == 200, created.text
    room_id = created.json()["channel_id"]

    def queued() -> set[str]:
        return {item["channel_id"] for item in client.get("/api/v1/admin/queue", headers=headers(admin)).json()["channels"]}

    assert room_id in queued()
    assert client.delete("/api/v1/me", headers=headers(owner)).status_code == 200
    assert room_id not in queued()  # 原来会一直挂着，管理员点「通过」还会让它以「已注销」名义上线
    assert client.get("/api/v1/admin/stats", headers=headers(admin)).json()["pending_channels"] == 0
    with client.session_factory() as session:
        assert session.get(Channel, room_id).review_status == "rejected"


def test_audit_log_names_its_target(client):
    admin = register(client, "audit-admin@example.com", admin=True)
    register(client, "promoted@example.com")
    target = user_id(client, "promoted@example.com")
    assert client.post(f"/api/v1/admin/users/{target}/admin", headers=headers(admin), json={"is_admin": True}).status_code == 200

    items = client.get("/api/v1/admin/audit", headers=headers(admin)).json()["items"]
    granted = next(item for item in items if item["target_id"] == target)
    assert granted["target_label"] == "promoted"  # 以前只有一串 id，看不出是谁

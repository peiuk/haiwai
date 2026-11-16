"""私信列表：整批查询后预览、未读数、拉黑过滤照旧；已接受的会话不受「不接收陌生人私信」影响。"""
from tests.test_h5_domain import headers, register


def _me(client, token):
    return client.get("/api/v1/me", headers=headers(token)).json()["user_id"]


def test_inbox_preview_unread_and_blocked(client):
    me = register(client, "inbox-me@example.com", "我")
    alice = register(client, "inbox-alice@example.com", "阿丽")
    bob = register(client, "inbox-bob@example.com", "阿博")
    me_id = _me(client, me)
    for token, text in ((alice, "第一条"), (alice, "第二条"), (bob, "你好")):
        sent = client.post("/api/v1/me/messages", headers=headers(token), json={"to_user_id": me_id, "body": text})
        assert sent.status_code == 200, sent.text

    inbox = client.get("/api/v1/me/messages", headers=headers(me)).json()
    by_peer = {item["peer_name"]: item for item in inbox["items"]}
    assert by_peer["阿丽"]["preview"] == "第二条" and by_peer["阿丽"]["unread"] == 2
    assert by_peer["阿博"]["unread"] == 1 and inbox["request_count"] == 2

    client.put(f"/api/v1/me/blocks/{_me(client, bob)}", headers=headers(me))
    names = [item["peer_name"] for item in client.get("/api/v1/me/messages", headers=headers(me)).json()["items"]]
    assert names == ["阿丽"]


def test_accepted_thread_survives_turning_off_stranger_dms(client):
    sender = register(client, "dm-sender@example.com", "发信人")
    receiver = register(client, "dm-receiver@example.com", "收信人")
    receiver_id = _me(client, receiver)
    thread_id = client.post(
        "/api/v1/me/messages", headers=headers(sender), json={"to_user_id": receiver_id, "body": "你好"}
    ).json()["thread_id"]
    assert client.post(f"/api/v1/me/messages/{thread_id}/accept", headers=headers(receiver)).status_code == 200
    client.patch("/api/v1/me/prefs", headers=headers(receiver), json={"dm_allow_strangers": False})

    again = client.post("/api/v1/me/messages", headers=headers(sender), json={"to_user_id": receiver_id, "body": "还在吗"})
    assert again.status_code == 200, again.text
    assert again.json()["thread_id"] == thread_id

    stranger = register(client, "dm-stranger@example.com", "陌生人")
    blocked = client.post("/api/v1/me/messages", headers=headers(stranger), json={"to_user_id": receiver_id, "body": "嗨"})
    assert blocked.json()["code"] == "STRANGER_DM_CLOSED"

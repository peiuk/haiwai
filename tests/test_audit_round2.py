"""审计后补的两条：上传每日上限；注销账号时留言一并移除。"""

from app.api.v1 import uploads
from tests.test_h5_domain import approve, headers, housing_channel, register, verify


def test_upload_slots_are_capped_per_day(client, monkeypatch):
    monkeypatch.setattr(uploads, "DAILY_SLOTS", 2)
    user = register(client, "uploader@example.com")
    for _ in range(2):
        key = client.post("/api/v1/uploads/sign", headers=headers(user), json={"content_type": "image/png"}).json()["object_key"]
        assert client.put(f"/api/v1/uploads/{key}", headers=headers(user), content=b"png").status_code == 200
    refused = client.post("/api/v1/uploads/sign", headers=headers(user), json={"content_type": "image/png"})
    assert refused.status_code == 429 and refused.json()["code"] == "UPLOAD_DAILY_LIMIT"


def test_erasing_account_removes_its_comments(client):
    author = register(client, "post-author@example.com", "作者")
    verify(client, author, "+447700900811")
    leaver = register(client, "leaver@example.com", "要走的人")
    created = client.post(
        "/api/v1/contents", headers=headers(author), json={"channel_id": housing_channel(client), "title": "周末聚会", "body": "欢迎来"}
    )
    content_id = created.json()["content_id"]
    approve(client, author, content_id)
    reply = client.post(f"/api/v1/contents/{content_id}/comments", headers=headers(leaver), json={"body": "我的电话是 07700 900000"})
    assert reply.status_code == 200, reply.text
    comment_id = reply.json()["comment_id"]
    if reply.json()["status"] == "pending":
        done = client.post(f"/api/v1/moderation/comments/{comment_id}/decision", headers=headers(author), json={"decision": "approve"})
        assert done.status_code == 200, done.text
    assert [item["id"] for item in client.get(f"/api/v1/contents/{content_id}/comments").json()["items"]] == [comment_id]

    assert client.delete("/api/v1/me", headers=headers(leaver)).status_code == 200
    assert client.get(f"/api/v1/contents/{content_id}/comments").json()["items"] == []

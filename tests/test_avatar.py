"""用户上传头像：设置、在各处带出、换图时删旧文件、不能用别人的图或视频、后台能移除。"""

from tests.test_admin import headers, register

PNG = b"\x89PNG\r\n\x1a\nfake"


def upload(client, token, content_type="image/png"):
    key = client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": content_type}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=PNG).status_code == 200
    return key


def set_avatar(client, token, key):
    return client.patch("/api/v1/me", headers=headers(token), json={"avatar_key": key})


def test_user_sets_replaces_and_removes_avatar(client):
    user = register(client, "avatar-user@example.com")
    first = upload(client, user)
    saved = set_avatar(client, user, first)
    assert saved.status_code == 200, saved.text
    assert saved.json()["avatar_key"] == first
    user_id = saved.json()["user_id"]
    assert client.get(f"/api/v1/users/{user_id}").json()["avatar_key"] == first

    second = upload(client, user)
    assert set_avatar(client, user, second).json()["avatar_key"] == second
    assert client.get(f"/api/v1/uploads/{first}").status_code == 404  # 旧头像文件删掉，不留垃圾
    assert client.get(f"/api/v1/uploads/{second}").status_code == 200

    assert set_avatar(client, user, "").json()["avatar_key"] == ""
    assert client.get(f"/api/v1/uploads/{second}").status_code == 404


def test_avatar_must_be_own_stored_image(client):
    user = register(client, "avatar-own@example.com")
    other = register(client, "avatar-other@example.com")
    assert set_avatar(client, user, upload(client, other)).status_code == 400  # 别人的图
    assert set_avatar(client, user, upload(client, user, "video/mp4")).json()["code"] == "AVATAR_NOT_IMAGE"
    assert client.get("/api/v1/me", headers=headers(user)).json()["avatar_key"] == ""


def test_admin_removes_avatar_and_user_is_told(client):
    admin = register(client, "avatar-admin@example.com", admin=True)
    user = register(client, "avatar-bad@example.com")
    key = upload(client, user)
    user_id = set_avatar(client, user, key).json()["user_id"]
    assert client.get(f"/api/v1/admin/users/{user_id}", headers=headers(admin)).json()["avatar_key"] == key

    removed = client.post(f"/api/v1/admin/users/{user_id}/avatar/remove", headers=headers(admin), json={"reason": "违规图片"})
    assert removed.status_code == 200, removed.text
    assert client.get("/api/v1/me", headers=headers(user)).json()["avatar_key"] == ""
    assert client.get(f"/api/v1/uploads/{key}").status_code == 404
    notes = client.get("/api/v1/me/notifications", headers=headers(user)).json()
    assert "头像已被管理员移除" in str(notes)
    again = client.post(f"/api/v1/admin/users/{user_id}/avatar/remove", headers=headers(admin), json={})
    assert again.status_code == 409

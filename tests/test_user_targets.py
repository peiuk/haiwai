from datetime import datetime, timezone

from app.models import User
from tests.test_community import headers, register


def _me(client, token):
    return client.get("/api/v1/me", headers=headers(token)).json()["user_id"]


def test_follow_block_dm_reject_self_with_clear_message(client):
    me = register(client, "self@example.com", "自己")
    my_id = _me(client, me)

    for method, path, body in [
        ("PUT", f"/api/v1/me/follows/{my_id}", None),
        ("PUT", f"/api/v1/me/blocks/{my_id}", None),
        ("POST", "/api/v1/me/messages", {"to_user_id": my_id, "body": "hi"}),
    ]:
        response = client.request(method, path, json=body, headers=headers(me))
        assert response.status_code == 400, (path, response.text)
        assert response.json()["code"] == "CANNOT_TARGET_SELF"


def test_erasing_an_admin_account_drops_admin_rights(client):
    token = register(client, "leaving-admin@example.com", "要走的管理员")
    admin_id = _me(client, token)
    session = client.session_factory()
    person = session.get(User, admin_id)
    person.is_admin = person.is_super = True
    session.commit()
    session.close()

    assert client.delete("/api/v1/me", headers=headers(token)).status_code == 200
    session = client.session_factory()
    person = session.get(User, admin_id)
    assert (person.is_admin, person.is_super, person.totp_secret) == (False, False, None)
    session.close()


def test_deleted_account_cannot_be_followed_or_blocked_but_unfollow_still_works(client):
    me = register(client, "fan@example.com", "粉丝")
    gone = register(client, "gone@example.com", "已注销")
    gone_id = _me(client, gone)
    assert client.put(f"/api/v1/me/follows/{gone_id}", headers=headers(me)).status_code == 200

    session = client.session_factory()
    session.get(User, gone_id).deleted_at = datetime.now(timezone.utc)
    session.commit()
    session.close()

    assert client.put(f"/api/v1/me/follows/{gone_id}", headers=headers(me)).status_code == 404
    assert client.put(f"/api/v1/me/blocks/{gone_id}", headers=headers(me)).status_code == 404
    unfollow = client.delete(f"/api/v1/me/follows/{gone_id}", headers=headers(me))
    assert unfollow.status_code == 200 and unfollow.json() == {"following": False}

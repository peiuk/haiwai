"""城市话题自动添加：注册填城市 → 发帖默认带上城市名作为话题之一，可删除/覆盖。"""
from tests.test_h5_domain import CONSENTS, headers, register, verify


def _register_with_city(client, email: str, city: str | None) -> str:
    payload = {
        "email": email,
        "password": "password-1",
        "display_name": "城市用户",
        "consents": CONSENTS,
    }
    if city is not None:
        payload["city_code"] = city
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_city_topic_auto_added_from_user_city(client):
    """用户注册填了城市 → 发帖不传 city_topic 时，自动带用户城市。"""
    token = _register_with_city(client, "city-auto@example.com", "伦敦")
    verify(client, token, "+447700900901")
    created = client.post(
        "/api/v1/contents",
        headers=headers(token),
        json={"title": "周末看房", "body": "周六下午去看房"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["city_topic"] == "伦敦"


def test_city_topic_removed_when_explicit_empty(client):
    """发帖显式传 city_topic="" 表示删除城市话题，不自动加。"""
    token = _register_with_city(client, "city-remove@example.com", "伦敦")
    verify(client, token, "+447700900902")
    created = client.post(
        "/api/v1/contents",
        headers=headers(token),
        json={"title": "随便聊聊", "body": "不想带城市", "city_topic": ""},
    )
    assert created.status_code == 200, created.text
    assert created.json()["city_topic"] == ""


def test_city_topic_overridden_by_explicit_value(client):
    """发帖显式传城市名 → 覆盖默认用户城市。"""
    token = _register_with_city(client, "city-override@example.com", "伦敦")
    verify(client, token, "+447700900903")
    created = client.post(
        "/api/v1/contents",
        headers=headers(token),
        json={"title": "曼城探店", "body": "去曼城吃火锅", "city_topic": "曼城"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["city_topic"] == "曼城"


def test_city_topic_absent_when_user_has_no_city(client):
    """用户注册未填城市 → 发帖不带城市话题。"""
    token = register(client, "city-none@example.com", "无城市用户")
    verify(client, token, "+447700900904")
    created = client.post(
        "/api/v1/contents",
        headers=headers(token),
        json={"title": "普通帖子", "body": "没有城市"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["city_topic"] == ""

from app.models import Channel
from tests.test_rooms import headers, register, verify

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def test_validator_message_reaches_the_client(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "1234", "display_name": "短", "consents": CONSENTS},
    )
    assert response.status_code == 422
    body = response.json()
    # 前端只读 code / message；原来这里只有 detail，用户看到的是「请求没有成功」
    assert body["code"] == "VALIDATION_FAILED"
    assert body["message"] == "密码至少 8 位"
    assert body["detail"]


def test_listing_fields_are_bounded_to_column_width(client):
    host = register(client, "long-host@example.com")
    verify(client, host, "+447700900811")
    session = client.session_factory()
    market = Channel(code="g-market-l", name_hans="市场", name_hant="市场", kind="official_curated", category="市场", region_code="GLOBAL", is_active=True)
    session.add(market)
    session.commit()
    market_id = market.id
    session.close()
    base = {"channel_id": market_id, "title": "书桌", "body": "九成新书桌转让", "category": "市场", "kind": "secondhand",
            "area": "伦敦", "price_amount": "40", "price_unit": "", "contact": "sms: 1", "attrs": {}}

    too_long = client.post("/api/v1/listings", headers=headers(host), json={**base, "area": "伦" * 81})
    assert too_long.status_code == 422
    assert too_long.json()["message"] == "内容太长了，最多 80 个字"

    ok = client.post("/api/v1/listings", headers=headers(host), json=base)
    assert ok.status_code == 200, ok.text

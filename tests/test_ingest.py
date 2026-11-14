from app.models import Channel, Content


CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


def test_fixture_ingest_dedups_degrades_and_clusters(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "reader-ingest@example.com", "password": "password-1", "display_name": "读者", "consents": CONSENTS},
    )
    assert registered.status_code == 200, registered.text
    token = registered.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session = client.session_factory()
    visa = Channel(
        code="uk-visa",
        name_hans="签证与政策",
        name_hant="簽證與政策",
        kind="official_auto",
        region_code="UK",
        is_active=True,
    )
    housing = Channel(
        code="uk-housing",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    session.add_all([visa, housing])
    session.commit()
    visa_id, housing_id = visa.id, housing.id
    session.close()
    assert client.put(f"/api/v1/me/subscriptions/{visa_id}", headers=headers).status_code == 200
    assert client.put(f"/api/v1/me/subscriptions/{housing_id}", headers=headers).status_code == 200

    first = client.post("/api/v1/admin/ingest/fixture", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"created": 3, "duplicates": 0, "degraded": 3}
    second = client.post("/api/v1/admin/ingest/fixture", headers=headers)
    assert second.json()["created"] == 0
    assert second.json()["duplicates"] == 3

    session = client.session_factory()
    rows = session.query(Content).filter(Content.type == "news").all()
    session.close()
    assert len(rows) == 3
    for row in rows:
        assert row.body is None
        assert row.canonical_url
        assert row.summary and len(row.summary) <= 200
        assert "SECRET FULL TEXT" not in (row.summary or "")
        assert row.ai_status == "degraded"
        assert row.licence_ref == "OGL v3.0"

    visa_stream = client.get(f"/api/v1/channels/{visa_id}/items").json()["items"]
    housing_stream = client.get(f"/api/v1/channels/{housing_id}/items").json()["items"]
    assert any("签证" in item["title"] for item in visa_stream)
    assert any("押金" in item["title"] for item in housing_stream)
    assert all("签证" not in item["title"] for item in housing_stream)

    feed = client.get("/api/v1/me/feed", headers=headers).json()["items"]
    clustered = [item for item in feed if item["source_count"] == 2]
    assert len(clustered) == 1
    urls = {source["canonical_url"] for source in clustered[0]["sources"]}
    assert urls == {"https://www.gov.uk/visa-fees", "https://www.gov.uk/visa-fees-extra"}


def test_llm_failure_still_ingests(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fail")
    from app.core.config import get_settings

    get_settings.cache_clear()
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "llm-down@example.com", "password": "password-1", "display_name": "读者", "consents": CONSENTS},
    )
    token = registered.json()["access_token"]
    session = client.session_factory()
    session.add_all(
        [
            Channel(
                code="uk-visa",
                name_hans="签证与政策",
                name_hant="簽證與政策",
                kind="official_auto",
                region_code="UK",
                is_active=True,
            ),
            Channel(
                code="uk-housing",
                name_hans="英国租房",
                name_hant="英國租房",
                kind="official_curated",
                region_code="UK",
                is_active=True,
            ),
        ]
    )
    session.commit()
    session.close()
    response = client.post("/api/v1/admin/ingest/fixture", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 3
    assert response.json()["degraded"] == 3
    get_settings.cache_clear()

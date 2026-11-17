"""分类信息：价格面议、招聘按小时 / 天 / 周 / 月、最多 6 张图。"""
from app.models import Channel, ListingExt
from tests.test_h5_domain import headers, housing_channel, register, verify


def _jobs_channel(client) -> str:
    with client.session_factory() as session:
        channel = Channel(code="uk-jobs-list", name_hans="英国招聘", name_hant="英國招聘", kind="official_curated", category="招聘", region_code="UK", is_active=True)
        session.add(channel)
        session.commit()
        return channel.id


def _image(client, token: str) -> str:
    key = client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": "image/png"}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=b"\x89PNG").status_code == 200
    return key


def test_negotiable_price_job_units_and_six_images(client):
    author = register(client, "price-author@example.com")
    verify(client, author, "+447700900931")
    housing = housing_channel(client)

    def post(**extra):
        body = {"channel_id": housing, "title": "单间", "body": "近地铁", "category": "房产", "kind": "rent",
                "area": "Newcastle", "price_amount": "900", "price_unit": "月", "contact": "微信 abc", **extra}
        return client.post("/api/v1/listings", headers=headers(author), json=body)

    # 面议：不带单位也能发，存下来就是「面议」
    negotiable = post(price_amount="面议", price_unit="")
    assert negotiable.status_code == 200, negotiable.text
    with client.session_factory() as session:
        ext = session.get(ListingExt, negotiable.json()["content_id"])
        assert (ext.price_amount, ext.price_unit) == ("面议", None)

    jobs = _jobs_channel(client)
    for unit in ("小时", "天", "周", "月"):
        assert post(channel_id=jobs, category="招聘", kind="job", price_amount="12", price_unit=unit).status_code == 200
    assert post(channel_id=jobs, category="招聘", kind="job", price_amount="12", price_unit="年").status_code == 400

    keys = [_image(client, author) for _ in range(7)]
    assert post(image_keys=keys[:6]).status_code == 200
    assert post(image_keys=keys).status_code == 422

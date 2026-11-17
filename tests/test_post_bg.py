"""彩色背景帖：只能选预设、只给 130 字以内不带图视频的文字帖；编辑时能换 / 去掉；详情带上。"""
from tests.test_h5_domain import headers, register, verify


def _author(client):
    token = register(client, "bg-author@example.com", "作者")
    verify(client, token, "+447700900461")
    return token


def _post(client, token, **extra):
    return client.post("/api/v1/contents", headers=headers(token), json={"title": "今天天气真好", "body": "今天天气真好", **extra})


def _bg(client, token, content_id):
    return client.get(f"/api/v1/contents/{content_id}", headers=headers(token)).json()["bg_style"]


def test_short_text_post_keeps_background(client):
    token = _author(client)
    created = _post(client, token, bg_style="purple")
    assert created.status_code == 200, created.text
    assert _bg(client, token, created.json()["content_id"]) == "purple"
    assert _bg(client, token, _post(client, token).json()["content_id"]) == ""


def test_background_rejected_for_unknown_long_or_media_posts(client):
    token = _author(client)
    assert _post(client, token, bg_style="rainbow").status_code == 422  # 不在预设里
    too_long = client.post("/api/v1/contents", headers=headers(token), json={"title": "长", "body": "字" * 131, "bg_style": "red"})
    assert too_long.status_code == 400
    assert _post(client, token, bg_style="red", post_type="video").status_code == 400  # 视频帖不能加背景


def test_edit_can_change_or_drop_background(client):
    token = _author(client)
    content_id = _post(client, token, bg_style="blue").json()["content_id"]

    def edit(body: str = "改了", **extra):
        return client.patch(f"/api/v1/contents/{content_id}", headers=headers(token), json={"title": "改了", "body": body, **extra})

    assert edit(bg_style="yellow").status_code == 200
    assert _bg(client, token, content_id) == "yellow"
    assert edit("字" * 131, bg_style="yellow").status_code == 400
    assert edit().status_code == 200  # 不带 bg_style = 去掉背景
    assert _bg(client, token, content_id) == ""

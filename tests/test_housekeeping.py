"""每日清理：放弃的上传名额、没用上的文件删掉；用在帖子、头像、多图列表里的文件保留。"""
import json
from datetime import timedelta

from sqlalchemy import update

from app.api.v1 import uploads
from app.housekeeping import run_housekeeping
from app.models import Content, RateHit, UploadObject, User, utcnow
from tests.test_h5_domain import headers, register


def _upload(client, token: str) -> str:
    key = client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": "image/png"}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=headers(token), content=b"\x89PNG\r\n\x1a\nimg").status_code == 200
    return key


def test_housekeeping_removes_only_unused_uploads(client, tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "upload_root", lambda: tmp_path)
    token = register(client, "keeper@example.com")
    avatar, in_list, unused = _upload(client, token), _upload(client, token), _upload(client, token)
    abandoned = client.post("/api/v1/uploads/sign", headers=headers(token), json={"content_type": "image/png"}).json()["object_key"]
    fresh = _upload(client, token)  # 才传上来：可能还在写草稿，不能删

    session = client.session_factory()
    user = session.query(User).filter_by(email="keeper@example.com").one()
    user.avatar_key = avatar
    session.add(Content(type="post", title="多图", status="published", author_id=user.id, image_keys_json=json.dumps([in_list])))
    old = utcnow() - timedelta(days=8)
    session.execute(update(UploadObject).where(UploadObject.key != fresh).values(created_at=old))
    session.add(RateHit(key="login:old", at=old))
    session.commit()

    assert run_housekeeping(session) == {"unused_uploads_removed": 1}

    left = {row.key for row in session.query(UploadObject)}
    assert left == {avatar, in_list, fresh}  # unused 和 abandoned 没了
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([avatar, in_list, fresh])
    assert abandoned not in left and unused not in left
    assert session.query(RateHit).count() == 0
    session.close()

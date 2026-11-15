"""配置了对象存储（S3 协议）时：上传转存过去、读取跳转到媒体域名、存储出错不算上传成功。"""
import pytest

from app.api.v1 import uploads
from app.core.config import get_settings
from app.models import UploadObject

CONSENTS = [
    {"purpose": "tos", "version": "2026-11-08", "granted": True},
    {"purpose": "privacy", "version": "2026-11-08", "granted": True},
]


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.fail = False

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        if self.fail:
            raise ConnectionError("storage down")
        self.objects[(Bucket, Key)] = (Body.read(), ContentType)  # Body 是打开的文件，流式上传

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setenv("S3_ENDPOINT", "https://s3.example.test")
    monkeypatch.setenv("S3_BUCKET", "media")
    monkeypatch.setenv("MEDIA_PUBLIC_URL", "https://media.example.test/media/")
    get_settings.cache_clear()
    monkeypatch.setattr(uploads, "_s3_client", lambda *args: fake)
    yield fake
    monkeypatch.undo()
    get_settings.cache_clear()


def register(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "media@example.com", "password": "password-1", "display_name": "媒体", "consents": CONSENTS},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def sign(client, auth) -> str:
    return client.post("/api/v1/uploads/sign", headers=auth, json={"content_type": "image/png"}).json()["object_key"]


def test_upload_goes_to_object_storage_and_reads_redirect(client, s3, tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "upload_root", lambda: tmp_path)
    auth = register(client)
    key = sign(client, auth)

    assert client.put(f"/api/v1/uploads/{key}", headers=auth, content=b"\x89PNGdata").status_code == 200
    assert s3.objects == {("media", key): (b"\x89PNGdata", "image/png")}
    assert list(tmp_path.iterdir()) == []  # 没有落到本地磁盘，临时文件也清掉了

    read = client.get(f"/api/v1/uploads/{key}", follow_redirects=False)
    assert read.status_code == 302
    assert read.headers["location"] == f"https://media.example.test/media/{key}"
    # 已存过的不能覆盖：这条规则不因为换了存储而失效
    assert client.put(f"/api/v1/uploads/{key}", headers=auth, content=b"other").status_code == 409


def test_storage_failure_is_not_reported_as_success(client, s3):
    auth = register(client)
    key = sign(client, auth)
    s3.fail = True
    failed = client.put(f"/api/v1/uploads/{key}", headers=auth, content=b"\x89PNGdata")
    assert failed.status_code == 503 and failed.json()["code"] == "STORAGE_UNAVAILABLE"
    with client.session_factory() as session:
        assert session.get(UploadObject, key).stored is False
    assert client.get(f"/api/v1/uploads/{key}", follow_redirects=False).status_code == 404
    assert not list(uploads.upload_root().glob("*.part"))  # 失败后不留临时文件
    s3.fail = False  # 存储恢复后同一个名额可以重传
    assert client.put(f"/api/v1/uploads/{key}", headers=auth, content=b"\x89PNGdata").status_code == 200


def test_delete_object_removes_it_from_storage(client, s3):
    auth = register(client)
    key = sign(client, auth)
    client.put(f"/api/v1/uploads/{key}", headers=auth, content=b"\x89PNGdata")
    assert ("media", key) in s3.objects
    uploads.delete_object(key)  # 注销账号时 me.py 对每个上传调用它
    assert s3.objects == {}


def test_public_url_defaults_to_endpoint_and_bucket(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT", "https://s3.example.test/")
    monkeypatch.setenv("S3_BUCKET", "media")
    monkeypatch.delenv("MEDIA_PUBLIC_URL", raising=False)
    get_settings.cache_clear()
    try:
        assert uploads.public_url("abc") == "https://s3.example.test/media/abc"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()

"""上传的图片转 WebP（缩到 2048、转正、去 EXIF），视频转 720p MP4；解不开的文件不能存。"""
import io
import shutil
import subprocess

import pytest
from PIL import Image

from app import media
from app.api.v1 import uploads
from app.models import UploadObject
from tests.test_object_storage import register


def jpeg(width: int, height: int, orientation: int | None = None) -> bytes:
    buf = io.BytesIO()
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPS 纬度：上传后必须去掉
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_image_becomes_small_upright_webp_without_exif(tmp_path):
    source = tmp_path / "a.part"
    source.write_bytes(jpeg(4000, 3000, orientation=6))  # 6 = 需要顺时针转 90°
    out, content_type = media.compress(source, "image/jpeg")
    assert content_type == "image/webp"
    with Image.open(out) as img:
        assert img.format == "WEBP"
        assert img.size == (1536, 2048)  # 转正后是竖图，长边缩到 2048
        assert not img.getexif()


def test_png_transparency_kept(tmp_path):
    source = tmp_path / "a.part"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(source, "PNG")
    out, _ = media.compress(source, "image/png")
    with Image.open(out) as img:
        assert img.mode == "RGBA" and img.getpixel((0, 0))[3] == 0


def test_broken_image_rejected(tmp_path):
    source = tmp_path / "a.part"
    source.write_bytes(b"\x89PNG\r\n\x1a\nnot really")
    with pytest.raises(media.MediaError):
        media.compress(source, "image/png")
    assert not (tmp_path / "a.webp").exists()


def test_upload_endpoint_stores_webp(client, tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "compress", media.compress)  # 取消 conftest 里的跳过
    monkeypatch.setattr(uploads, "upload_root", lambda: tmp_path)
    auth = register(client)
    key = client.post("/api/v1/uploads/sign", headers=auth, json={"content_type": "image/jpeg"}).json()["object_key"]
    assert client.put(f"/api/v1/uploads/{key}", headers=auth, content=jpeg(100, 50)).status_code == 200
    assert sorted(p.name for p in tmp_path.iterdir()) == [key]  # 临时文件和转码中间文件都清掉了
    with Image.open(tmp_path / key) as img:
        assert img.format == "WEBP"
    with client.session_factory() as session:
        assert session.get(UploadObject, key).content_type == "image/webp"
    read = client.get(f"/api/v1/uploads/{key}")
    assert read.headers["content-type"] == "image/webp"

    bad = client.post("/api/v1/uploads/sign", headers=auth, json={"content_type": "image/png"}).json()["object_key"]
    failed = client.put(f"/api/v1/uploads/{bad}", headers=auth, content=b"\x89PNG\r\n\x1a\nbroken")
    assert failed.status_code == 400 and failed.json()["code"] == "UPLOAD_INVALID"
    with client.session_factory() as session:
        assert session.get(UploadObject, bad).stored is False


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="本机没装 ffmpeg")
def test_video_becomes_720p_mp4(tmp_path):
    source = tmp_path / "v.part"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=10", "-t", "1",
         "-c:v", "libx264", "-f", "mov", str(source)],
        check=True,
    )
    out, content_type = media.compress(source, "video/quicktime")
    assert content_type == "video/mp4"
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert probe.stdout.strip() == "1280,720"


def test_video_kept_as_is_without_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    source = tmp_path / "v.part"
    source.write_bytes(b"\x00\x00\x00\x18ftyp")
    assert media.compress(source, "video/webm") == (source, "video/webm")

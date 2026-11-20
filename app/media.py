"""上传的图片转 WebP、视频转 720p MP4，再存到对象存储：存储费和流量都省下大半。"""
import logging
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

IMAGE_MAX_SIDE = 2048  # 长边超过就等比缩小；手机原图 4000px 在网页上看不出区别
IMAGE_MAX_PIXELS = 60_000_000  # 解码前先看尺寸：5MB 的 PNG 也能声明几亿像素，解开会撑爆内存
VIDEO_SHORT_SIDE = 720  # 短边（横屏的高、竖屏的宽）超过就缩到 720，要 1080p 改这里
VIDEO_TIMEOUT = 240  # 秒；要比 web/nginx.conf 的 proxy_read_timeout 300s 短，超时给用户明确的错误


class MediaError(Exception):
    """文件解不开或转不了：按"文件不是图片 / 视频"处理。"""


def compress(source: Path, content_type: str) -> tuple[Path, str]:
    """返回 (压缩后的文件, 新的类型)。会阻塞，异步接口里要放到线程池跑。"""
    if content_type.startswith("image/"):
        return _to_webp(source), "image/webp"
    return _to_mp4(source, content_type)


def _to_webp(source: Path) -> Path:
    out = source.with_suffix(".webp")
    try:
        with Image.open(source) as img:
            if img.width * img.height > IMAGE_MAX_PIXELS:
                raise MediaError("图片像素太多")
            # 手机照片按 EXIF 方向转正；另存时不带 EXIF，顺便去掉了拍摄地点（GPS）
            img = ImageOps.exif_transpose(img)
            img.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
            img.save(out, "WEBP", quality=80, method=4)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        out.unlink(missing_ok=True)
        raise MediaError("图片无法解码") from exc
    return out


def _to_mp4(source: Path, content_type: str) -> tuple[Path, str]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        # shortcut: 本机开发没装 ffmpeg 时按原文件存；Docker 镜像里装了（见 Dockerfile），线上一定会转码
        log.warning("没有找到 ffmpeg，视频按原文件存储，没有压缩")
        return source, content_type
    out = source.with_suffix(".mp4")
    side = VIDEO_SHORT_SIDE
    # 只缩不放大；-2 / trunc(...)*2 保证宽高是偶数（H.264 的要求）
    scale = (
        f"scale='if(gt(iw,ih),-2,trunc(min({side},iw)/2)*2)'"
        f":'if(gt(iw,ih),trunc(min({side},ih)/2)*2,-2)'"
    )
    cmd = [
        ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1",  # 去掉拍摄地点等元数据
        "-vf", scale, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",  # 索引放文件头：浏览器不用下完整个文件就能开始播
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=VIDEO_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        out.unlink(missing_ok=True)
        raise MediaError("视频太长，处理超时") from exc
    except subprocess.CalledProcessError as exc:
        out.unlink(missing_ok=True)
        log.info("ffmpeg 转码失败: %s", exc.stderr.decode(errors="replace")[-500:])
        raise MediaError("视频无法解码") from exc
    return out, "video/mp4"

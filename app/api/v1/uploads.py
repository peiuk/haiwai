from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.models import UploadObject, User, new_id, utcnow

router = APIRouter(prefix="/uploads")
MAX_OPEN_SLOTS = 20
DAILY_SLOTS = 100  # 一个人 24 小时内最多申请这么多次上传：不然循环传 100MB 视频能把磁盘写满
LIMITS = {
    "image/jpeg": 5_000_000,
    "image/png": 5_000_000,
    "image/webp": 5_000_000,
    "video/mp4": 100_000_000,
    "video/webm": 100_000_000,
    "video/quicktime": 100_000_000,
}


class SignBody(BaseModel):
    content_type: str

    @field_validator("content_type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in LIMITS:
            raise ValueError("只接受 jpeg、png、webp、mp4、webm 或 mov")
        return value


def upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


@lru_cache
def _s3_client(endpoint: str, access_key: str, secret_key: str, region: str):
    import boto3  # 只在配置了对象存储时才用到
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        # MinIO 等自建存储用路径风格（endpoint/bucket/key），不用 bucket 子域名
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def _s3():
    """配置了对象存储就返回 (client, bucket)，否则 None（用本地磁盘）。"""
    settings = get_settings()
    if not settings.s3_endpoint.strip():
        return None
    client = _s3_client(settings.s3_endpoint.strip(), settings.s3_access_key, settings.s3_secret_key, settings.s3_region)
    return client, settings.s3_bucket


def public_url(key: str) -> str:
    settings = get_settings()
    base = settings.media_public_url.strip() or f"{settings.s3_endpoint.strip().rstrip('/')}/{settings.s3_bucket}"
    return f"{base.rstrip('/')}/{key}"


# 文件内容永不变，但删除（下架、注销）后 CDN 节点上的副本要在这个时间内过期，所以只缓存 1 天。
# shortcut: 删除后最多 1 天内仍可能从 CDN 打开；要立即生效时在 delete_object 里调用 CDN 的清缓存接口。
MEDIA_CACHE = "public, max-age=86400"


def save_object(key: str, source: Path, content_type: str) -> None:
    """把已经收完的临时文件 source 存成 key：本地磁盘直接改名，对象存储则流式上传。会阻塞，异步接口里要放到线程池跑。"""
    remote = _s3()
    if remote is None:
        source.replace(upload_root() / key)
        return
    client, bucket = remote
    try:
        with source.open("rb") as body:
            client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type, CacheControl=MEDIA_CACHE)
    except Exception as exc:  # 存储服务器连不上、密钥不对等：让用户稍后再试，不能当成上传成功
        raise APIError(503, "STORAGE_UNAVAILABLE", "存储服务暂时不可用，请稍后再试") from exc


def delete_object(key: str) -> None:
    remote = _s3()
    if remote is None:
        (upload_root() / key).unlink(missing_ok=True)
        return
    client, bucket = remote
    try:
        client.delete_object(Bucket=bucket, Key=key)
    except Exception as exc:  # 删不掉就不能说"已删除"：注销账号承诺了连文件一起删
        raise APIError(503, "STORAGE_UNAVAILABLE", "存储服务暂时不可用，请稍后再试") from exc


def _safe_key(key: str) -> str:
    if len(key) != 32 or any(ch not in "0123456789abcdef" for ch in key):
        raise APIError(404, "UPLOAD_NOT_FOUND", "图片不存在")
    return key


def owned_upload(session: Session, user: User, key: str) -> UploadObject:
    row = session.get(UploadObject, key)
    if row is None or row.owner_id != user.id or not row.stored:
        raise APIError(400, "UPLOAD_NOT_READY", "图片还没上传完成")
    return row


@router.post("/sign")
def sign_upload(
    body: SignBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    # 没传完的名额数量封顶：不然可以无限申请，撑爆数据库。
    waiting = session.scalar(
        select(func.count()).select_from(UploadObject).where(UploadObject.owner_id == user.id, UploadObject.stored.is_(False))
    )
    if (waiting or 0) >= MAX_OPEN_SLOTS:
        raise APIError(429, "UPLOAD_SLOTS_FULL", "还有太多没传完的上传，请先完成或稍后再试")
    today = session.scalar(
        select(func.count())
        .select_from(UploadObject)
        .where(UploadObject.owner_id == user.id, UploadObject.created_at >= utcnow() - timedelta(hours=24))
    )
    if (today or 0) >= DAILY_SLOTS:
        raise APIError(429, "UPLOAD_DAILY_LIMIT", "今天上传得太多了，请明天再试")
    key = new_id().replace("-", "")
    session.add(UploadObject(key=key, owner_id=user.id, content_type=body.content_type, stored=False))
    session.commit()
    return {"object_key": key, "upload_url": f"/api/v1/uploads/{key}", "content_type": body.content_type}


@router.put("/{key}")
async def store_upload(
    key: str,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    key = _safe_key(key)
    row = session.get(UploadObject, key)
    if row is None or row.owner_id != user.id:
        raise APIError(404, "UPLOAD_NOT_FOUND", "没有这个上传名额")
    # 已存过的文件不能再覆盖：否则帖子审核通过后，作者可以往同一个 key 传别的文件，悄悄换掉已审核的内容。
    if row.stored:
        raise APIError(409, "UPLOAD_ALREADY_STORED", "这个文件已经上传过，请重新申请上传名额")
    limit = LIMITS[row.content_type]
    kind = "视频" if row.content_type.startswith("video/") else "图片"
    too_big = APIError(400, "UPLOAD_INVALID", f"{kind}不能为空，且不能超过 {limit // 1_000_000}MB")
    # 先看声明的大小，再边读边数：超限立刻停，不把整个请求体读进内存。
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_big
    # 边收边写到临时文件，内存里只留一个数据块（100MB 的视频不再整个读进内存）。
    temp = upload_root() / f"{key}.part"
    size = 0
    try:
        with temp.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise too_big
                out.write(chunk)
        if size == 0:
            raise too_big
        # 传到对象存储可能要几十秒：放到线程池，不然这个进程在此期间处理不了别的请求。
        await run_in_threadpool(save_object, key, temp, row.content_type)
    finally:
        temp.unlink(missing_ok=True)  # 本地存储时已经改名走了；失败或走对象存储时清掉临时文件
    row.stored = True
    session.commit()
    return {"stored": True}


@router.get("/{key}", response_model=None)
def read_upload(key: str, session: Session = Depends(get_db)) -> Response:
    key = _safe_key(key)
    row = session.get(UploadObject, key)
    if row is None or not row.stored:
        raise APIError(404, "UPLOAD_NOT_FOUND", "图片不存在")
    if _s3() is not None:
        # 文件在对象存储上：让浏览器直接去媒体域名取，流量不经过这台服务器
        return RedirectResponse(public_url(key), status_code=302, headers={"Cache-Control": MEDIA_CACHE})
    path = upload_root() / key
    if not path.is_file():
        raise APIError(404, "UPLOAD_NOT_FOUND", "图片不存在")
    return FileResponse(path, media_type=row.content_type, headers={"Cache-Control": MEDIA_CACHE})

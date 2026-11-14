from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.models import UploadObject, User, new_id

router = APIRouter(prefix="/uploads")
MAX_OPEN_SLOTS = 20
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
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_big
        chunks.append(chunk)
    payload = b"".join(chunks)
    if not payload:
        raise too_big
    path = upload_root() / key
    path.write_bytes(payload)
    row.stored = True
    session.commit()
    return {"stored": True}


@router.get("/{key}")
def read_upload(key: str, session: Session = Depends(get_db)) -> FileResponse:
    key = _safe_key(key)
    row = session.get(UploadObject, key)
    path = upload_root() / key
    if row is None or not row.stored or not path.is_file():
        raise APIError(404, "UPLOAD_NOT_FOUND", "图片不存在")
    return FileResponse(path, media_type=row.content_type)

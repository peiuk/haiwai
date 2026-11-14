from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.models import UploadObject, User, new_id

router = APIRouter(prefix="/uploads")
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
    payload = await request.body()
    limit = LIMITS[row.content_type]
    kind = "视频" if row.content_type.startswith("video/") else "图片"
    if not payload or len(payload) > limit:
        raise APIError(400, "UPLOAD_INVALID", f"{kind}不能为空，且不能超过 {limit // 1_000_000}MB")
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

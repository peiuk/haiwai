from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.api.v1.me import active_channel
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.config import get_settings
from app.embed import POLICY_VERSION, PROVIDERS, embed_url_for, inspect_source, rechecked_status, resolve_embed_url
from app.models import ChannelItem, Content, User, UserConsentLog, utcnow

router = APIRouter()


class ResolveBody(BaseModel):
    url: str


class EmbedPostBody(BaseModel):
    url: str
    title: str
    note: str = ""

    @field_validator("title", "note")
    @classmethod
    def lengths(cls, value: str) -> str:
        text = value.strip()
        if len(text) > 500:
            raise ValueError("外链说明不能超过 500 字")
        return text


class ConsentBody(BaseModel):
    scope: str

    @field_validator("scope")
    @classmethod
    def known_scope(cls, value: str) -> str:
        if value not in {"once", "always", "withdrawn"}:
            raise ValueError("同意范围不正确")
        return value


def _visible_embed(session: Session, content_id: str, user: User) -> Content:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None or content.type != "embed" or content.embed_status == "none":
        raise APIError(404, "CONTENT_NOT_FOUND", "外链不存在")
    if content.status != "published" and content.author_id != user.id:
        raise APIError(404, "CONTENT_NOT_FOUND", "外链不存在")
    return content


def _latest_scope(session: Session, user_id: str, provider_code: str) -> str | None:
    row = session.scalar(
        select(UserConsentLog)
        .where(UserConsentLog.user_id == user_id, UserConsentLog.provider_code == provider_code)
        .order_by(UserConsentLog.created_at.desc())
    )
    return row.scope if row else None


@router.post("/embed/resolve")
def resolve_embed(body: ResolveBody, _user: User = Depends(current_user)) -> dict[str, object]:
    return resolve_embed_url(body.url)


@router.post("/channels/{channel_id}/items/embed")
def create_embed(
    channel_id: str,
    body: EmbedPostBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    if not user.phone_verified:
        raise APIError(403, "PHONE_NOT_VERIFIED", "发布前需要先验证手机")
    if not body.title:
        raise APIError(400, "VALIDATION_FAILED", "标题不能为空")
    channel = active_channel(session, channel_id)
    resolved = resolve_embed_url(body.url)
    now = utcnow()
    content = Content(
        type="embed",
        status="pending",
        author_id=user.id,
        title=body.title,
        summary=body.note[:500] or None,
        body=body.note,
        canonical_url=str(resolved["source_url"]),
        source_name=str(resolved["display_name"]),
        embed_provider_code=str(resolved["provider_code"]),
        embed_media_id=str(resolved["media_id"]),
        embed_source_url=str(resolved["source_url"]),
        embed_status=str(resolved["embed_status"]),
    )
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, added_at=now))
    write_audit(session, user.id, "embed.create", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status, "embed_status": content.embed_status}


@router.get("/embed/{content_id}/consent")
def get_embed_consent(
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = _visible_embed(session, content_id, user)
    provider = PROVIDERS.get(content.embed_provider_code or "")
    scope = _latest_scope(session, user.id, content.embed_provider_code or "")
    may_load = content.embed_status == "embeddable" and content.status == "published" and scope == "always"
    payload: dict[str, object] = {
        "provider_code": content.embed_provider_code,
        "display_name": provider["display_name"] if provider else "",
        "notice": provider["notice"] if provider else "",
        "policy_version": POLICY_VERSION,
        "scope": scope,
        "embed_status": content.embed_status,
        "source_url": content.embed_source_url,
        "may_load": may_load,
    }
    if may_load:
        payload["embed_url"] = embed_url_for(content.embed_provider_code or "", content.embed_media_id or "")
    return payload


@router.post("/embed/{content_id}/consent")
def set_embed_consent(
    content_id: str,
    body: ConsentBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = _visible_embed(session, content_id, user)
    if content.embed_status != "embeddable" or content.status != "published":
        raise APIError(409, "EMBED_FRAMING_BLOCKED", "这条链接不能在站内播放")
    session.add(
        UserConsentLog(
            user_id=user.id,
            provider_code=content.embed_provider_code or "",
            scope=body.scope,
            policy_version=POLICY_VERSION,
        )
    )
    write_audit(session, user.id, "embed.consent", "content", content.id)
    session.commit()
    payload: dict[str, object] = {"scope": body.scope, "may_load": body.scope in {"once", "always"}}
    if payload["may_load"]:
        payload["embed_url"] = embed_url_for(content.embed_provider_code or "", content.embed_media_id or "")
    return payload


@router.post("/embed/recheck")
def recheck_embeds(_user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, int]:
    if get_settings().app_env != "dev":
        raise APIError(404, "NOT_FOUND", "没有这个功能")
    rows = session.scalars(
        select(Content).where(Content.type == "embed", Content.deleted_at.is_(None), Content.embed_source_url.is_not(None))
    ).all()
    changed = 0
    for content in rows:
        nxt = rechecked_status(content.embed_status, inspect_source(content.embed_source_url or ""))
        if nxt != content.embed_status:
            content.embed_status = nxt
            changed += 1
    session.commit()
    return {"checked": len(rows), "changed": changed}

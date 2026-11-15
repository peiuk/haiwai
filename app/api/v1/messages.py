import json
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.api.v1.uploads import owned_upload
from app.core.db import get_db
from app.core.errors import APIError
from app.models import Content, DmMessage, DmThread, ListingExt, Notification, User, UserBlock, UserFollow, utcnow

router = APIRouter()


class PrefBody(BaseModel):
    dm_allow_strangers: bool


class MessageBody(BaseModel):
    to_user_id: str
    body: str = ""
    listing_id: str | None = None
    image_key: str | None = None

    @field_validator("body")
    @classmethod
    def body_length(cls, value: str) -> str:
        text = value.strip()
        if len(text) > 1000:
            raise ValueError("私信需要 1 到 1000 个字")
        return text


class ReplyBody(BaseModel):
    body: str = ""
    image_key: str | None = None

    @field_validator("body")
    @classmethod
    def body_length(cls, value: str) -> str:
        text = value.strip()
        if len(text) > 1000:
            raise ValueError("私信需要 1 到 1000 个字")
        return text


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _blocked(session: Session, a: str, b: str) -> bool:
    return (
        session.get(UserBlock, (a, b)) is not None or session.get(UserBlock, (b, a)) is not None
    )


def _thread_for(session: Session, user: User, other_id: str) -> DmThread | None:
    low, high = _pair(user.id, other_id)
    return session.scalar(select(DmThread).where(DmThread.user_low == low, DmThread.user_high == high))


@router.get("/me/prefs")
def get_prefs(user: User = Depends(current_user)) -> dict[str, bool]:
    return {"dm_allow_strangers": user.dm_allow_strangers}


@router.patch("/me/prefs")
def update_prefs(
    body: PrefBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    user.dm_allow_strangers = body.dm_allow_strangers
    session.commit()
    return {"dm_allow_strangers": user.dm_allow_strangers}


@router.put("/me/follows/{target_id}")
def follow(target_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, bool]:
    if target_id == user.id or session.get(User, target_id) is None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if session.get(UserFollow, (user.id, target_id)) is None:
        session.add(UserFollow(user_id=user.id, target_id=target_id))
        session.commit()
    return {"following": True}


@router.delete("/me/follows/{target_id}")
def unfollow(target_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, bool]:
    if target_id == user.id or session.get(User, target_id) is None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    row = session.get(UserFollow, (user.id, target_id))
    if row is not None:
        session.delete(row)
        session.commit()
    return {"following": False}


@router.get("/me/blocks")
def list_blocks(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, list[dict[str, str]]]:
    rows = session.scalars(select(UserBlock).where(UserBlock.user_id == user.id)).all()
    items: list[dict[str, str]] = []
    for row in rows:
        person = session.get(User, row.target_id)
        if person is None:
            continue
        items.append({"user_id": person.id, "display_name": person.display_name})
    return {"items": items}


@router.put("/me/blocks/{target_id}")
def block(target_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, bool]:
    if target_id == user.id or session.get(User, target_id) is None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if session.get(UserBlock, (user.id, target_id)) is None:
        session.add(UserBlock(user_id=user.id, target_id=target_id))
        session.commit()
    return {"blocked": True}


@router.delete("/me/blocks/{target_id}")
def unblock(target_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, bool]:
    row = session.get(UserBlock, (user.id, target_id))
    if row is not None:
        session.delete(row)
        session.commit()
    return {"blocked": False}


@router.get("/me/messages")
def list_messages(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    rows = session.scalars(
        select(DmThread).where(or_(DmThread.user_low == user.id, DmThread.user_high == user.id))
    ).all()
    items: list[dict[str, object]] = []
    for thread in rows:
        other_id = thread.user_high if thread.user_low == user.id else thread.user_low
        if _blocked(session, user.id, other_id):
            continue
        peer = session.get(User, other_id)
        latest = session.scalar(
            select(DmMessage).where(DmMessage.thread_id == thread.id).order_by(DmMessage.created_at.desc())
        )
        unread = session.scalar(
            select(func.count())
            .select_from(DmMessage)
            .where(
                DmMessage.thread_id == thread.id,
                DmMessage.sender_id != user.id,
                DmMessage.read_at.is_(None),
            )
        )
        preview = ""
        updated_at = thread.created_at
        if latest is not None:
            updated_at = latest.created_at
            text = "[图片]" if latest.kind == "image" else latest.body
            preview = f"我：{text}" if latest.sender_id == user.id else text
        items.append(
            {
                "thread_id": thread.id,
                "peer_id": other_id,
                "peer_name": peer.display_name if peer else "",
                "peer_handle": peer.handle or "" if peer else "",
                "peer_tone": peer.avatar_tone if peer else "a",
                "peer_avatar": peer.avatar_key or "" if peer else "",
                "status": thread.status,
                "listing_inquiry": thread.listing_inquiry,
                "listing_ref": json.loads(thread.listing_ref) if thread.listing_ref else None,
                "preview": preview,
                "updated_at": updated_at.isoformat(),
                "unread": int(unread or 0),
            }
        )
    items.sort(key=lambda item: str(item["updated_at"]), reverse=True)
    return {"items": items, "request_count": sum(1 for item in items if item["status"] == "request")}


@router.post("/me/messages")
def open_message(
    body: MessageBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    peer = session.get(User, body.to_user_id)
    if peer is None or peer.id == user.id or peer.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if _blocked(session, user.id, peer.id):
        raise APIError(403, "USER_BLOCKED", "无法发送私信")
    kind, image_key = _message_payload(session, user, body.body, body.image_key)
    listing_ref = None
    snapshot = None
    inquiry = False
    if body.listing_id:
        ext = session.get(ListingExt, body.listing_id)
        listed_content = session.get(Content, body.listing_id)
        # 只能就「对方自己发的」分类信息咨询，否则任何房源 id 都能绕过「不接收陌生人私信」。
        if (
            ext is None
            or ext.closed_reason
            or listed_content is None
            or listed_content.status != "published"
            or listed_content.author_id != peer.id
        ):
            raise APIError(404, "CONTENT_NOT_FOUND", "这条分类信息不存在")
        inquiry = True
        snapshot = {
            "id": body.listing_id,
            "title": listed_content.title,
            "price": ext.price_amount,
            "unit": ext.price_unit or "",
            "currency": ext.currency,
            "area": ext.area,
            "image_key": listed_content.image_key or "",
        }
        listing_ref = json.dumps(snapshot, ensure_ascii=False)
    followed = session.get(UserFollow, (peer.id, user.id)) is not None
    if inquiry:
        status = "active"
    elif followed:
        status = "active"
    elif peer.dm_allow_strangers:
        status = "request"
    else:
        raise APIError(403, "STRANGER_DM_CLOSED", "对方不接收陌生人私信")
    thread = _thread_for(session, user, peer.id)
    if thread is None:
        low, high = _pair(user.id, peer.id)
        thread = DmThread(
            user_low=low,
            user_high=high,
            status=status,
            listing_inquiry=inquiry,
            listing_ref=listing_ref,
        )
        session.add(thread)
        session.flush()
    elif inquiry:
        thread.status = "active"
        thread.listing_inquiry = True
        thread.listing_ref = listing_ref
    if thread.status == "request" and not inquiry:
        first = session.scalar(select(DmMessage).where(DmMessage.thread_id == thread.id).order_by(DmMessage.created_at))
        if first is not None and first.sender_id != user.id:
            raise APIError(403, "DM_REQUEST_PENDING", "接受前不能回复")
    session.add(DmMessage(thread_id=thread.id, sender_id=user.id, kind=kind, body=body.body, image_key=image_key))
    if inquiry:
        session.add(
            Notification(user_id=peer.id, kind="dm.listing", body="有人就分类信息向你咨询", content_id=body.listing_id)
        )
    session.commit()
    opened: dict[str, object] = {"thread_id": thread.id, "status": thread.status}
    if snapshot is not None:
        opened["listing_ref"] = snapshot
        opened["suggested_text"] = "你好，想了解一下这套房源是否还在？"
    return opened


@router.post("/me/messages/{thread_id}")
def reply_message(
    thread_id: str,
    body: ReplyBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    thread = session.get(DmThread, thread_id)
    if thread is None or user.id not in {thread.user_low, thread.user_high}:
        raise APIError(404, "THREAD_NOT_FOUND", "会话不存在")
    other_id = thread.user_high if thread.user_low == user.id else thread.user_low
    if _blocked(session, user.id, other_id):
        raise APIError(403, "USER_BLOCKED", "无法发送私信")
    kind, image_key = _message_payload(session, user, body.body, body.image_key)
    if thread.status == "request":
        first = session.scalar(select(DmMessage).where(DmMessage.thread_id == thread.id).order_by(DmMessage.created_at))
        if first is not None and first.sender_id != user.id:
            raise APIError(403, "DM_REQUEST_PENDING", "接受前不能回复")
    session.add(DmMessage(thread_id=thread.id, sender_id=user.id, kind=kind, body=body.body, image_key=image_key))
    session.commit()
    return {"thread_id": thread.id, "status": thread.status}


DM_PER_MINUTE = 10
DM_PER_HOUR = 100


def _message_payload(session: Session, user: User, text: str, image_key: str | None) -> tuple[str, str | None]:
    now = utcnow()
    for window, limit in ((timedelta(minutes=1), DM_PER_MINUTE), (timedelta(hours=1), DM_PER_HOUR)):
        sent = session.scalar(
            select(func.count())
            .select_from(DmMessage)
            .where(DmMessage.sender_id == user.id, DmMessage.created_at >= now - window)
        )
        if (sent or 0) >= limit:
            raise APIError(429, "RATE_LIMITED", "私信发得太频繁，请稍后再试")
    if image_key:
        owned_upload(session, user, image_key)
        return "image", image_key
    if not text:
        raise APIError(400, "VALIDATION_FAILED", "私信需要文字或图片")
    return "text", None


@router.get("/me/messages/{thread_id}")
def thread_messages(
    thread_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    thread = session.get(DmThread, thread_id)
    if thread is None or user.id not in {thread.user_low, thread.user_high}:
        raise APIError(404, "THREAD_NOT_FOUND", "会话不存在")
    other_id = thread.user_high if thread.user_low == user.id else thread.user_low
    if _blocked(session, user.id, other_id):
        raise APIError(403, "USER_BLOCKED", "无法查看这个会话")
    rows = session.scalars(
        select(DmMessage).where(DmMessage.thread_id == thread.id).order_by(DmMessage.created_at)
    ).all()
    return {
        "thread_id": thread.id,
        "status": thread.status,
        "items": [
            {
                "id": row.id,
                "sender_id": row.sender_id,
                "kind": row.kind,
                "body": row.body,
                "image_key": row.image_key,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.post("/me/messages/{thread_id}/accept")
def accept_message(
    thread_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    thread = session.get(DmThread, thread_id)
    if thread is None or user.id not in {thread.user_low, thread.user_high}:
        raise APIError(404, "THREAD_NOT_FOUND", "会话不存在")
    first = session.scalar(select(DmMessage).where(DmMessage.thread_id == thread.id).order_by(DmMessage.created_at))
    if first is None or first.sender_id == user.id:
        raise APIError(403, "DM_REQUEST_PENDING", "只有收到请求的人可以接受")
    thread.status = "active"
    session.commit()
    return {"thread_id": thread.id, "status": thread.status}


@router.delete("/me/messages/{thread_id}")
def delete_message_request(
    thread_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    thread = session.get(DmThread, thread_id)
    if thread is None or user.id not in {thread.user_low, thread.user_high}:
        raise APIError(404, "THREAD_NOT_FOUND", "会话不存在")
    if thread.status != "request":
        raise APIError(409, "DM_ALREADY_ACTIVE", "进行中的会话不能这样删除")
    first = session.scalar(select(DmMessage).where(DmMessage.thread_id == thread.id).order_by(DmMessage.created_at))
    if first is None or first.sender_id == user.id:
        raise APIError(403, "DM_REQUEST_PENDING", "只有收到请求的人可以删除")
    session.execute(delete(DmMessage).where(DmMessage.thread_id == thread.id))
    session.delete(thread)
    session.commit()
    return {"deleted": True}


@router.post("/me/messages/{thread_id}/read")
def mark_message_read(
    thread_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    thread = session.get(DmThread, thread_id)
    if thread is None or user.id not in {thread.user_low, thread.user_high}:
        raise APIError(404, "THREAD_NOT_FOUND", "会话不存在")
    rows = session.scalars(
        select(DmMessage).where(
            DmMessage.thread_id == thread.id,
            DmMessage.sender_id != user.id,
            DmMessage.read_at.is_(None),
        )
    ).all()
    now = utcnow()
    for row in rows:
        row.read_at = now
    session.commit()
    return {"marked": len(rows)}

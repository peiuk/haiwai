import re
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user, optional_user
from app.api.v1.uploads import owned_upload
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.feed import author_names
from app.guard import first_status
from app.privacy import is_room_member, require_not_blocked_by
from app.recommend import country_blocked, is_roaming
from app.rooms import require_not_banned
from app.reports import ReportBody, limit_reports, report_receipt
from app.models import (
    Channel,
    ChannelCollaborator,
    ChannelItem,
    ChannelSubscription,
    Content,
    RoomBan,
    ModerationCase,
    CommentLike,
    Notification,
    RoomComment,
    RoomJoinRequest,
    User,
    UserFollow,
    as_utc,
    utcnow,
)

router = APIRouter(prefix="/channels")
_MENTION = re.compile(r"(?:^|(?<=\s))@([A-Za-z0-9_](?:[A-Za-z0-9._]{0,18}[A-Za-z0-9_])?)")
_MENTION_ANY = re.compile(r"(?:^|(?<=\s))@([\w\u4e00-\u9fff]{1,40})")
_KEYWORD = re.compile(r"#([\w\u4e00-\u9fff_]{1,12})")


def mention_count(body: str) -> int:
    return min(10, len(_MENTION_ANY.findall(body)))


def mention_handles(body: str) -> list[str]:
    found: list[str] = []
    for handle in _MENTION.findall(body):
        token = handle.lower()
        if token not in found:
            found.append(token)
        if len(found) == 10:
            break
    return found


def mention_users(session: Session, body: str) -> list[User]:
    users: list[User] = []
    for handle in mention_handles(body):
        person = session.scalar(
            select(User).where(User.handle == handle, User.deleted_at.is_(None), User.status == "active")
        )
        if person is not None:
            users.append(person)
    return users


def mentioned_handles(session: Session, bodies: list[str]) -> set[str]:
    """一批留言里 @ 到的、真实存在的用户名，一次查完（列表接口原来每条留言每个 @ 各查一次库）。"""
    wanted = {handle for body in bodies for handle in mention_handles(body)}
    if not wanted:
        return set()
    return set(
        session.scalars(
            select(User.handle).where(User.handle.in_(wanted), User.deleted_at.is_(None), User.status == "active")
        ).all()
    )


def publish_comment(session: Session, comment: RoomComment) -> None:
    """留言公开（审核通过，或关了审核直接发布）：改状态，并通知被 @ 到且关注了作者的人。"""
    comment.status = "published"
    author = session.get(User, comment.author_id)
    name = author.display_name if author else "有人"
    for person in mention_users(session, comment.body):
        if person.id == comment.author_id:
            continue
        if session.get(UserFollow, (person.id, comment.author_id)) is None:
            continue
        session.add(
            Notification(
                user_id=person.id,
                kind="mention",
                body=f"{name} 在留言里提到了你"[:200],
                content_id=comment.content_id,
            )
        )
    # 回复通知也等留言公开了才发：待审的回复别人看不到，先通知等于绕过审核往作者那里推东西
    content = session.get(Content, comment.content_id) if comment.content_id else None
    if content is not None and content.author_id and content.author_id != comment.author_id:
        session.add(
            Notification(user_id=content.author_id, kind="reply", body=f"{name} 回复了「{content.title}」"[:200], content_id=content.id)
        )


def apply_comment_like(session: Session, user: User, comment: RoomComment) -> dict[str, object]:
    existing = session.get(CommentLike, (comment.id, user.id))
    if existing is None:
        session.add(CommentLike(comment_id=comment.id, user_id=user.id))
        liked = True
    else:
        session.delete(existing)
        liked = False
    session.commit()
    count = session.scalar(select(func.count()).select_from(CommentLike).where(CommentLike.comment_id == comment.id))
    return {"liked": liked, "like_count": int(count or 0)}


def comment_like_state(session: Session, user: User | None, comment_ids: list[str]) -> tuple[dict[str, int], set[str]]:
    if not comment_ids:
        return {}, set()
    counts = {
        comment_id: int(count)
        for comment_id, count in session.execute(
            select(CommentLike.comment_id, func.count())
            .where(CommentLike.comment_id.in_(comment_ids))
            .group_by(CommentLike.comment_id)
        ).all()
    }
    liked: set[str] = set()
    if user is not None:
        liked = set(
            session.scalars(
                select(CommentLike.comment_id).where(
                    CommentLike.comment_id.in_(comment_ids),
                    CommentLike.user_id == user.id,
                )
            ).all()
        )
    return counts, liked


class CommentBody(BaseModel):
    body: str
    content_id: str | None = None
    parent_id: str | None = None
    image_key: str | None = None

    @field_validator("body")
    @classmethod
    def body_length(cls, value: str) -> str:
        if len(value) > 1000:
            raise ValueError("留言需要 1 到 1000 个字")
        return value

    @model_validator(mode="after")
    def require_text_or_image(self) -> "CommentBody":
        if not self.body.strip() and not self.image_key:
            raise ValueError("留言需要文字或一张图片")
        return self


def _room(session: Session, channel_id: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None or channel.kind != "room" or not channel.is_active:
        raise APIError(404, "CHANNEL_NOT_FOUND", "房间不存在")
    return channel


def _can_view(session: Session, room: Channel, user: User | None) -> bool:
    return not room.is_private or is_room_member(session, room, user)


@router.get("/{channel_id}/comments")
def list_comments(
    channel_id: str,
    cursor: str | None = None,
    limit: int = 20,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    room = _room(session, channel_id)
    if not _can_view(session, room, user):
        raise APIError(403, "ROOM_PRIVATE", "这个房间需要先加入")
    bounded = min(max(limit, 1), 50)
    # 在数据库里按 (时间, id) 翻页，每页只读一页：原来每次把整个房间的留言读进内存再截取。
    query = (
        select(RoomComment)
        .where(
            RoomComment.room_id == room.id,
            RoomComment.removed_at.is_(None),
            (RoomComment.status == "published")
            | ((RoomComment.status == "pending") & (RoomComment.author_id == (user.id if user else ""))),
        )
        .order_by(RoomComment.created_at.desc(), RoomComment.id.desc())
    )
    parts = decode_cursor(cursor) if cursor else None
    after_at = parse_added_at(parts[1]) if parts and len(parts) == 2 else None
    if parts and after_at is not None:
        query = query.where(
            or_(
                RoomComment.created_at < after_at,
                and_(RoomComment.created_at == after_at, RoomComment.id < parts[0]),
            )
        )
    rows = session.scalars(query.limit(bounded + 1)).all()
    page = rows[:bounded]
    next_cursor = encode_cursor(page[-1].id, page[-1].created_at.isoformat()) if len(rows) > bounded else None
    counts, liked = comment_like_state(session, user, [row.id for row in page])
    authors = author_names(session, [row.author_id for row in page])
    real_handles = mentioned_handles(session, [row.body for row in page])
    items: list[dict[str, object]] = []
    for row in page:
        author_name, author_handle = authors.get(row.author_id, ("", ""))[:2]  # 第三项是头像，这里不显示
        items.append(
            {
                "id": row.id,
                "author_id": row.author_id,
                "author_name": author_name,
                "author_handle": author_handle,
                "body": row.body,
                "image_key": row.image_key,
                "content_id": row.content_id,
                "parent_id": row.parent_id,
                "mention_count": row.mention_count,
                "mentions": [handle for handle in mention_handles(row.body) if handle in real_handles],
                "keyword_count": row.keyword_count,
                "like_count": counts.get(row.id, 0),
                "liked": row.id in liked,
                "status": row.status,
                "can_delete": user is not None and user.id in (row.author_id, room.owner_id),
                "created_at": row.created_at.isoformat(),
            }
        )
    payload: dict[str, object] = {"items": items}
    if next_cursor:
        payload["next_cursor"] = next_cursor
    return payload


@router.post("/{channel_id}/comments")
def create_comment(
    channel_id: str,
    body: CommentBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    if is_roaming(session, user):
        raise APIError(403, "ROAMING_READONLY", "跨国漫游下仅供浏览，发帖请切换至本地")
    if country_blocked(session, user, room):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    if not _can_view(session, room, user):
        raise APIError(403, "ROOM_PRIVATE", "这个房间需要先加入")
    require_not_banned(session, [room.id], user.id)
    if body.content_id and body.parent_id:
        raise APIError(400, "VALIDATION_FAILED", "留言不能同时挂在帖子和另一条留言上")
    replying_to: list[str | None] = []
    if body.content_id:
        item = session.get(ChannelItem, (room.id, body.content_id))
        if item is None:
            raise APIError(404, "CONTENT_NOT_FOUND", "这条内容不在房间里")
        target = session.get(Content, body.content_id)
        replying_to.append(target.author_id if target else None)
    if body.parent_id:
        parent = session.get(RoomComment, body.parent_id)
        if parent is None or parent.room_id != room.id or parent.removed_at is not None:
            raise APIError(404, "COMMENT_NOT_FOUND", "要回复的留言不存在")
        replying_to.append(parent.author_id)
    require_not_blocked_by(session, replying_to, user.id)
    if body.image_key:
        owned_upload(session, user, body.image_key)
    now = utcnow()
    recent = session.scalars(
        select(RoomComment.created_at).where(RoomComment.room_id == room.id, RoomComment.author_id == user.id)
    ).all()
    if sum(1 for created_at in recent if as_utc(created_at) >= now - timedelta(minutes=1)) >= 5:
        raise APIError(429, "RATE_LIMITED", "留言太频繁")
    if sum(1 for created_at in recent if as_utc(created_at) >= now - timedelta(hours=1)) >= 20:
        raise APIError(429, "RATE_LIMITED", "这个小时的留言已达上限")
    comment = RoomComment(
        room_id=room.id,
        content_id=body.content_id,
        parent_id=body.parent_id,
        author_id=user.id,
        body=body.body,
        image_key=body.image_key,
        mention_count=mention_count(body.body),
        keyword_count=min(5, len(_KEYWORD.findall(body.body))),
    )
    session.add(comment)
    session.flush()
    if first_status(session, "comment", body.body, user=user) == "published":
        publish_comment(session, comment)
    write_audit(session, user.id, "comment.create", "comment", comment.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@router.post("/{channel_id}/comments/{comment_id}/like")
def toggle_comment_like(
    channel_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    room = _room(session, channel_id)
    if not _can_view(session, room, user):
        raise APIError(403, "ROOM_PRIVATE", "这个房间需要先加入")
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.room_id != room.id or comment.removed_at is not None or comment.status != "published":
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    return apply_comment_like(session, user, comment)


@router.post("/{channel_id}/comments/{comment_id}/report")
def report_comment(
    channel_id: str,
    comment_id: str,
    body: ReportBody,
    request: Request,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    limit_reports(session, request, user)
    room = _room(session, channel_id)
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.room_id != room.id or comment.removed_at is not None or comment.status != "published":
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if user is not None and comment.author_id == user.id:
        raise APIError(403, "SELF_REPORT", "不能举报自己的留言")
    if user is not None:
        existing = session.scalar(
            select(ModerationCase.id).where(
                ModerationCase.reported_comment_id == comment.id,
                ModerationCase.reporter_id == user.id,
            )
        )
        if existing:
            raise APIError(409, "DUPLICATE_REPORT", "你已经举报过这条留言")
    else:
        # 游客没法按人去重：同一条留言已有待处理的游客举报就直接复用。
        pending = session.scalar(
            select(ModerationCase).where(
                ModerationCase.reported_comment_id == comment.id,
                ModerationCase.reporter_id.is_(None),
                ModerationCase.status == "open",
            )
        )
        if pending is not None:
            return report_receipt(pending)
    case = ModerationCase(
        reported_comment_id=comment.id,
        reporter_id=user.id if user else None,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(case)
    session.flush()
    write_audit(session, user.id if user else None, "comment.report", "comment", comment.id)
    session.commit()
    return report_receipt(case)


@router.delete("/{channel_id}/comments/{comment_id}")
def remove_comment(
    channel_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.room_id != room.id:
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if comment.author_id != user.id and room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "不能处理这条留言")
    comment.status = "removed"
    comment.removed_at = utcnow()
    write_audit(session, user.id, "comment.remove", "comment", comment.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@router.post("/{channel_id}/join-requests")
def request_join(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    if country_blocked(session, user, room):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    if not room.is_private:
        raise APIError(409, "ROOM_PUBLIC", "公开房间直接加入即可")
    if room.owner_id == user.id or session.get(ChannelSubscription, (user.id, room.id)) is not None:
        raise APIError(409, "ALREADY_MEMBER", "你已经在这个房间里")
    if session.get(RoomBan, (room.id, user.id)) is not None:
        raise APIError(403, "ROOM_BANNED", "房主已把你移出这个房间，不能再申请加入")
    existing = session.scalar(
        select(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id, RoomJoinRequest.user_id == user.id)
    )
    if existing is None:
        existing = RoomJoinRequest(room_id=room.id, user_id=user.id)
        session.add(existing)
        session.commit()
    return {"request_id": existing.id, "status": "pending"}


@router.get("/{channel_id}/join-requests")
def list_join_requests(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, str]]]:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以查看申请")
    rows = session.scalars(select(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id)).all()
    people = {person.id: person for person in session.scalars(select(User).where(User.id.in_([row.user_id for row in rows] or [""]))).all()}
    return {"items": [
        {
            "request_id": row.id,
            "user_id": row.user_id,
            "display_name": people[row.user_id].display_name if row.user_id in people else "用户",
            "handle": people[row.user_id].handle if row.user_id in people else "",
        }
        for row in rows
    ]}


@router.post("/{channel_id}/join-requests/{request_id}/approve")
def approve_join(
    channel_id: str,
    request_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以通过申请")
    request = session.get(RoomJoinRequest, request_id)
    if request is None or request.room_id != room.id:
        raise APIError(404, "REQUEST_NOT_FOUND", "没有这条申请")
    if session.get(ChannelSubscription, (request.user_id, room.id)) is None:
        session.add(ChannelSubscription(user_id=request.user_id, channel_id=room.id))
        room.subscriber_count += 1
    session.delete(request)
    write_audit(session, user.id, "room.join.approve", "channel", room.id)
    session.commit()
    return {"joined": True}


@router.post("/{channel_id}/join-requests/{request_id}/reject")
def reject_join(
    channel_id: str,
    request_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以拒绝申请")
    request = session.get(RoomJoinRequest, request_id)
    if request is None or request.room_id != room.id:
        raise APIError(404, "REQUEST_NOT_FOUND", "没有这条申请")
    session.delete(request)
    write_audit(session, user.id, "room.join.reject", "channel", room.id)
    session.commit()
    return {"rejected": True}


# ---- 成员管理：房主移出成员并禁止再加入 ----


def _owned_room(session: Session, channel_id: str, user: User) -> Channel:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以管理成员")
    return room


def _people(session: Session, ids: list[str]) -> list[dict[str, str]]:
    rows = session.scalars(select(User).where(User.id.in_(ids or [""]), User.deleted_at.is_(None))).all()
    return [{"user_id": row.id, "display_name": row.display_name, "handle": row.handle or ""} for row in rows]


@router.get("/{channel_id}/members")
def list_members(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, str]]]:
    # shortcut: 一次返回全部成员，不分页；房间成员上千时改成分页
    room = _owned_room(session, channel_id, user)
    members = session.scalars(
        select(ChannelSubscription.user_id).where(
            ChannelSubscription.channel_id == room.id, ChannelSubscription.user_id != room.owner_id
        )
    ).all()
    banned = session.scalars(select(RoomBan.user_id).where(RoomBan.room_id == room.id)).all()
    return {"items": _people(session, list(members)), "banned": _people(session, list(banned))}


@router.put("/{channel_id}/bans/{member_id}")
def ban_member(
    channel_id: str,
    member_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    """移出房间并禁止再加入：成员关系、协作者身份、待审的加入申请一并清掉。"""
    room = _owned_room(session, channel_id, user)
    if member_id == room.owner_id or session.get(User, member_id) is None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    subscription = session.get(ChannelSubscription, (member_id, room.id))
    if subscription is not None:
        session.delete(subscription)
        room.subscriber_count = max(0, room.subscriber_count - 1)
    session.execute(
        delete(ChannelCollaborator).where(ChannelCollaborator.channel_id == room.id, ChannelCollaborator.user_id == member_id)
    )
    session.execute(delete(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id, RoomJoinRequest.user_id == member_id))
    if session.get(RoomBan, (room.id, member_id)) is None:
        session.add(RoomBan(room_id=room.id, user_id=member_id))
    write_audit(session, user.id, "room.member.ban", "channel", room.id, member_id)
    session.commit()
    return {"banned": True}


@router.delete("/{channel_id}/bans/{member_id}")
def unban_member(
    channel_id: str,
    member_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    room = _owned_room(session, channel_id, user)
    ban = session.get(RoomBan, (room.id, member_id))
    if ban is None:
        raise APIError(404, "USER_NOT_FOUND", "这个人没有被禁止加入")
    session.delete(ban)
    write_audit(session, user.id, "room.member.unban", "channel", room.id, member_id)
    session.commit()
    return {"banned": False}

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.v1.auth import optional_user
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.feed import embed_card, image_keys_of, reaction_flags
from app.keywords import load_keywords
from app.models import Channel, ChannelItem, Content, ModerationCase, User, UserBlock, UserFollow
from app.privacy import viewable
from app.rooms import ROOM_TYPE_LABELS
from app.reports import ReportBody, report_receipt

router = APIRouter()


def _profile(session: Session, user_id: str) -> User:
    profile = session.get(User, user_id)
    if profile is None or profile.deleted_at is not None or profile.status != "active":
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    return profile


@router.get("/users/{user_id}")
def public_profile(
    user_id: str,
    viewer: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    profile = _profile(session, user_id)
    following = False
    blocked = False
    if viewer is not None:
        following = session.get(UserFollow, (viewer.id, profile.id)) is not None
        blocked = session.get(UserBlock, (viewer.id, profile.id)) is not None
    return {
        "user_id": profile.id,
        "display_name": profile.display_name,
        "handle": profile.handle or "",
        "avatar_tone": profile.avatar_tone,
        "avatar_key": profile.avatar_key or "",
        "city_label": profile.city_label or "",
        "joined_at": profile.created_at.isoformat(),
        "post_count": _count(session, select(func.count()).select_from(Content).where(*_published(profile.id))),
        "follower_count": _count(session, select(func.count()).select_from(UserFollow).where(UserFollow.target_id == profile.id)),
        "following_count": _count(session, select(func.count()).select_from(UserFollow).where(UserFollow.user_id == profile.id)),
        "following": following,
        "blocked": blocked,
        "rooms": _rooms(session, profile, own=viewer is not None and viewer.id == profile.id),
    }


def _rooms(session: Session, profile: User, own: bool) -> list[dict[str, object]]:
    """这个人建的房间。别人只看到已上线的公开房间；本人还能看到私密的和审核中的（被拒的不列）。"""
    query = select(Channel).where(Channel.kind == "room", Channel.owner_id == profile.id, Channel.visibility == "public")
    if own:
        query = query.where(Channel.review_status != "rejected")
    else:
        query = query.where(Channel.is_active.is_(True), Channel.is_private.is_(False))
    return [
        {
            "id": room.id,
            "name_hans": room.name_hans,
            "room_type": room.room_type,
            "room_type_label": ROOM_TYPE_LABELS.get(room.room_type, room.room_type),
            "is_private": room.is_private,
            "pending": not room.is_active,
            "subscriber_count": room.subscriber_count,
        }
        for room in session.scalars(query.order_by(Channel.created_at.desc())).all()
    ]


def _count(session: Session, stmt: Select[tuple[int]]) -> int:
    return int(session.scalar(stmt) or 0)


def _published(user_id: str) -> tuple:
    # 私密房间的帖子在 SQL 里排除（主页对谁都不露）：先取 50 条再过滤，会被私密帖占满；帖子数也不该把它们算进去
    return (Content.author_id == user_id, Content.deleted_at.is_(None), Content.status == "published", viewable(None))


@router.post("/users/{user_id}/report")
def report_user(
    user_id: str,
    body: ReportBody,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    profile = _profile(session, user_id)
    if user is not None and profile.id == user.id:
        raise APIError(403, "SELF_REPORT", "不能举报自己")
    if user is not None:
        existing = session.scalar(
            select(ModerationCase.id).where(
                ModerationCase.reported_user_id == profile.id,
                ModerationCase.reporter_id == user.id,
            )
        )
        if existing:
            raise APIError(409, "DUPLICATE_REPORT", "你已经举报过这个用户")
    case = ModerationCase(
        reported_user_id=profile.id,
        reporter_id=user.id if user else None,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(case)
    session.flush()
    write_audit(session, user.id if user else None, "user.report", "user", profile.id)
    session.commit()
    return report_receipt(case)


@router.get("/users/{user_id}/posts")
def public_posts(
    user_id: str,
    viewer: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    profile = _profile(session, user_id)
    rows = session.scalars(
        select(Content)
        .where(*_published(profile.id))
        .order_by(Content.created_at.desc())
        .limit(50)  # shortcut: 主页只显示最近 50 条；要看更早的再加游标分页
    ).all()
    flags = reaction_flags(session, viewer.id if viewer else None, [row.id for row in rows])
    items: list[dict[str, object]] = []
    for row in rows:
        # 和搜索结果一样：帖子发在哪个频道（不算房间推送的副本），用于卡片上的频道名和转发
        placed = session.scalar(
            select(ChannelItem).where(ChannelItem.content_id == row.id, ChannelItem.origin_room_id.is_(None))
        )
        channel = session.get(Channel, placed.channel_id) if placed is not None else None
        liked, favorited = flags.get(row.id, (False, False))
        items.append(
            {
                "content_id": row.id,
                "title": row.title,
                "summary": row.summary,
                "type": row.type,
                "created_at": row.created_at.isoformat(),
                "source_name": row.source_name or "",
                "licence_ref": row.licence_ref or "",
                "canonical_url": row.canonical_url,
                "channel_id": channel.id if channel else None,
                "channel_name": channel.name_hans if channel else "",
                "keywords": load_keywords(row.keywords_json),
                "image_keys": image_keys_of(row),
                "video_key": row.video_key,
                "embed": embed_card(row),
                "liked": liked,
                "favorited": favorited,
            }
        )
    return {"items": items}

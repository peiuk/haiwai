"""管理后台：频道 / 房间和国家的管理。新增、编辑、删除频道和开关国家只有超级管理员能做。"""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin import PAGE, Reasoned, _count, _delete_files, _like, _names, _paged, _release_uploads, require_admin, require_super
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.regions import DEFAULT_REGIONS, open_regions
from app.models import (
    Channel,
    ChannelCollaborator,
    ChannelItem,
    ChannelSubscription,
    CommentLike,
    Content,
    ModerationCase,
    Region,
    RegionOpenRequest,
    RoomComment,
    RoomJoinRequest,
    RoomPostPush,
    User,
    UserRegionPref,
    utcnow,
)
from app.rooms import drop_pushes
from app.seed import ensure_region_channels

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.get("/channels")
def list_channels(q: str = "", region: str = "", page: int = 1, session: Session = Depends(get_db)) -> dict[str, object]:
    query = select(Channel)
    if region.strip():
        query = query.where(Channel.region_code == region.strip().upper())
    if q.strip():
        like = _like(q)
        query = query.where(or_(Channel.name_hans.ilike(like), Channel.code.ilike(like)))
    # 官方频道在前、按国家和排序号排，和前台看到的顺序一致；用户房间跟在后面
    rows, total = _paged(session, query, (Channel.kind == "room", Channel.region_code, Channel.sort_order, Channel.code), page)
    names = _names(session, [row.owner_id for row in rows])
    return {
        "total": total,
        "page_size": PAGE,
        "items": [
            {
                "channel_id": row.id,
                "code": row.code,
                "name": row.name_hans,
                "name_hant": row.name_hant,
                "kind": row.kind,
                "region_code": row.region_code,
                "category": row.category or "",
                "sort_order": row.sort_order,
                "owner_name": names.get(row.owner_id or "", ""),
                "is_active": row.is_active,
                "is_certified": row.is_certified,
                "certified": row.certified,
                "review_status": row.review_status,
                "subscriber_count": row.subscriber_count,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@router.get("/channel-options")
def channel_options(session: Session = Depends(get_db)) -> dict[str, list[dict[str, str]]]:
    """发公告时选频道用：所有上架的频道。"""
    rows = session.execute(
        select(Channel.id, Channel.name_hans).where(Channel.is_active.is_(True)).order_by(Channel.kind, Channel.name_hans).limit(200)
    ).all()
    return {"items": [{"channel_id": row.id, "name": row.name_hans} for row in rows]}


class CertifiedBody(BaseModel):
    certified: bool


@router.post("/channels/{channel_id}/certified")
def set_channel_certified(
    channel_id: str,
    body: CertifiedBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if (channel.kind or "").startswith("official"):
        raise APIError(409, "NO_CHANGE", "官方频道本来就带认证")
    if channel.is_certified == body.certified:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    channel.is_certified = body.certified
    write_audit(session, admin.id, "admin.channel.certify" if body.certified else "admin.channel.uncertify", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id, "certified": channel.certified}


class ChannelActiveBody(Reasoned):
    active: bool


@router.post("/channels/{channel_id}/active")
def set_channel_active(
    channel_id: str,
    body: ChannelActiveBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.is_active == body.active:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    channel.is_active = body.active
    action = "admin.channel.activate" if body.active else "admin.channel.deactivate"
    write_audit(session, admin.id, action, "channel", channel.id, body.note)
    session.commit()
    return {"channel_id": channel.id, "is_active": channel.is_active}


# ---- 频道新增 / 编辑 ----


class ChannelBody(BaseModel):
    name_hans: str = Field(min_length=1, max_length=64)
    name_hant: str = Field(default="", max_length=64)  # 留空则和简体名相同
    region_code: str
    category: str = Field(default="", max_length=16)
    sort_order: int = Field(default=0, ge=0, le=999)

    def apply(self, session: Session, channel: Channel) -> None:
        region = self.region_code.strip().upper()
        if region not in open_regions(session):
            raise APIError(422, "VALIDATION_FAILED", "只能选已开通的国家")
        channel.name_hans = self.name_hans.strip()
        channel.name_hant = self.name_hant.strip() or channel.name_hans
        channel.region_code = region
        channel.category = self.category.strip() or None
        channel.sort_order = self.sort_order


class ChannelCreateBody(ChannelBody):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,47}$")  # 频道的英文代号，建好后不能改
    kind: Literal["official_curated", "official_auto"] = "official_curated"


@router.post("/channels")
def create_channel(
    body: ChannelCreateBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    if session.scalar(select(Channel.id).where(Channel.code == body.code)) is not None:
        raise APIError(409, "DUPLICATE_CODE", "这个代号已经有频道在用了")
    channel = Channel(code=body.code, kind=body.kind, is_active=True, name_hans="", name_hant="")
    body.apply(session, channel)
    session.add(channel)
    session.flush()
    write_audit(session, admin.id, "admin.channel.create", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id}


@router.patch("/channels/{channel_id}")
def update_channel(
    channel_id: str,
    body: ChannelBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    body.apply(session, channel)
    write_audit(session, admin.id, "admin.channel.update", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id}


class ChannelDeleteBody(Reasoned):
    with_content: bool = False  # 频道非空时必须显式为 True
    confirm_name: str = ""  # 连内容一起删时要原样输入频道名


@router.post("/channels/{channel_id}/delete")
def delete_channel(
    channel_id: str,
    body: ChannelDeleteBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """彻底删除频道，不能恢复。

    空频道直接删。有内容的频道要显式带 with_content 并输入频道名确认：
    只属于这个频道的帖子一并下架，留言删掉，下属房间只解除归属（房间和里面的内容保留）。
    """
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    items = session.scalars(select(ChannelItem).where(ChannelItem.channel_id == channel.id)).all()
    comments = _count(session, RoomComment, RoomComment.room_id == channel.id)
    rooms = session.scalars(select(Channel).where(Channel.parent_channel_id == channel.id)).all()
    if items or comments or rooms:
        if not body.with_content:
            raise APIError(
                409,
                "CHANNEL_NOT_EMPTY",
                f"这个频道里还有 {len(items)} 条内容、{comments} 条留言、{len(rooms)} 个房间",
            )
        if body.confirm_name.strip() != channel.name_hans:
            raise APIError(422, "VALIDATION_FAILED", "输入的频道名不一致，没有删除")
    removed_posts, orphaned = _purge_channel(session, channel)
    # 频道删了以后日志里只剩 id，所以把名称、代号和删掉的数量写进备注
    detail = f"{channel.name_hans}（{channel.code}）"
    if items or comments or rooms:
        detail += f"，连同 {removed_posts} 条内容、{comments} 条留言，解除 {len(rooms)} 个房间的归属"
    detail += f"：{body.note}" if body.note else ""
    write_audit(session, admin.id, "admin.channel.delete", "channel", channel.id, detail[:300])
    session.commit()
    return {
        "deleted": True,
        "removed_posts": removed_posts,
        "removed_comments": comments,
        "detached_rooms": len(rooms),
        "files_left": _delete_files(orphaned),
    }


def _purge_channel(session: Session, channel: Channel) -> tuple[int, list[str]]:
    """删掉频道及其内容（不提交）。返回（下架的帖子数，提交后要删的文件 key）。

    只属于这个频道的帖子下架，也挂在别的频道的只解除关系；留言删掉；下属房间只解除归属。
    """
    items = session.scalars(select(ChannelItem).where(ChannelItem.channel_id == channel.id)).all()
    rooms = session.scalars(select(Channel).where(Channel.parent_channel_id == channel.id)).all()
    removed_posts = 0
    orphaned: list[str] = []
    now = utcnow()
    elsewhere = set(
        session.scalars(
            select(ChannelItem.content_id).where(
                ChannelItem.content_id.in_([item.content_id for item in items]), ChannelItem.channel_id != channel.id
            )
        ).all()
    )
    for item in items:
        # 还挂在别的频道里的帖子只解除关系，在别处照常显示；只属于这里的才下架
        content = None if item.content_id in elsewhere else session.get(Content, item.content_id)
        if content is not None and content.deleted_at is None:
            content.status = "deleted"
            content.deleted_at = now
            drop_pushes(session, content.id)
            removed_posts += 1
        session.delete(item)
    # 留言带的图片：登记记录现在删，文件等提交后删（不删的话知道原链接的人还能打开）
    doomed = session.execute(select(RoomComment.id, RoomComment.image_key).where(RoomComment.room_id == channel.id)).all()
    orphaned = _release_uploads(session, [row.image_key for row in doomed])
    session.execute(delete(CommentLike).where(CommentLike.comment_id.in_([row.id for row in doomed])))
    session.execute(delete(RoomComment).where(RoomComment.room_id == channel.id))
    session.execute(delete(RoomPostPush).where((RoomPostPush.room_id == channel.id) | (RoomPostPush.channel_id == channel.id)))
    for room in rooms:
        room.parent_channel_id = None
    # 针对这个频道的未处理举报没有对象可处理了，直接结案
    for case in session.scalars(
        select(ModerationCase).where(ModerationCase.reported_channel_id == channel.id, ModerationCase.status == "open")
    ):
        case.status = "closed"
        case.decision = "remove"
        case.decided_at = now
    # 成员关系等附属记录一并清掉（SQLite 开发库没开外键级联，这里显式删）
    for model, column in (
        (ChannelSubscription, ChannelSubscription.channel_id),
        (ChannelCollaborator, ChannelCollaborator.channel_id),
        (RoomJoinRequest, RoomJoinRequest.room_id),
    ):
        session.execute(delete(model).where(column == channel.id))
    session.delete(channel)
    session.flush()
    return removed_posts, orphaned


# ---- 国家开通 ----


def _region_row(session: Session, code: str) -> Region:
    """取这个国家的记录；内置国家（英国 / 国际）还没有记录时按默认值建一条。"""
    row = session.get(Region, code)
    if row is None:
        if code not in DEFAULT_REGIONS:
            raise APIError(404, "REGION_NOT_FOUND", "没有这个国家")
        name, city = DEFAULT_REGIONS[code]
        row = Region(code=code, name_hans=name, city=city, is_open=True)
        session.add(row)
    return row


@router.get("/regions")
def list_regions(session: Session = Depends(get_db)) -> dict[str, object]:
    is_open = open_regions(session)
    closed = {row.code: (row.name_hans, row.city) for row in session.scalars(select(Region).where(Region.is_open.is_(False)))}
    counts = dict(session.execute(select(Channel.region_code, func.count()).where(Channel.kind != "room").group_by(Channel.region_code)).all())
    wanted = session.execute(
        select(RegionOpenRequest.region_code, func.count()).group_by(RegionOpenRequest.region_code).order_by(func.count().desc())
    ).all()
    return {
        "items": [
            {
                "code": code,
                "name": name,
                "city": city,
                "is_open": code in is_open,
                "channel_count": counts.get(code, 0),
            }
            for code, (name, city) in {**is_open, **closed}.items()
        ],
        # 用户申请开通、但还没开通的国家，按申请人数排
        "requests": [{"code": code, "count": count} for code, count in wanted if code not in is_open],
    }


class RegionBody(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z]{2,8}$")  # 国家代码，如 US、CA、AU
    name: str = Field(min_length=1, max_length=32)
    city: str = Field(default="", max_length=32)


@router.post("/regions")
def open_region(
    body: RegionBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """开通一个新国家，并自动建好它的默认频道（资讯、交流、招聘、房产、市场、商务）。"""
    code = body.code.upper()
    if code in open_regions(session):
        raise APIError(409, "NO_CHANGE", "这个国家已经开通")
    row = session.get(Region, code)
    if row is None:
        row = Region(code=code, name_hans="", is_open=True)
        session.add(row)
    row.name_hans = body.name.strip()
    row.city = body.city.strip()
    row.is_open = True
    created = ensure_region_channels(session, code, row.name_hans)
    write_audit(session, admin.id, "admin.region.open", "region", code)
    session.commit()
    return {"code": code, "channels": [channel.name_hans for channel in created]}


class RegionOpenBody(Reasoned):
    open: bool


@router.post("/regions/{code}/open")
def set_region_open(
    code: str,
    body: RegionOpenBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    code = code.upper()
    if code == "GLOBAL":
        raise APIError(409, "NO_CHANGE", "国际频道各国共享，不能关闭")
    if (code in open_regions(session)) == body.open:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    row = _region_row(session, code)
    row.is_open = body.open
    write_audit(session, admin.id, "admin.region.open" if body.open else "admin.region.close", "region", code, body.note)
    session.commit()
    return {"code": code, "is_open": row.is_open}


class RegionDeleteBody(Reasoned):
    confirm_name: str = ""  # 要原样输入国家名才删


@router.post("/regions/{code}/delete")
def delete_region(
    code: str,
    body: RegionDeleteBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """彻底删除一个国家，连同它的全部频道、房间和其中的内容，不能恢复。国际（GLOBAL）各国共享，不能删。

    选了这个国家的用户回到国际。英国是内置国家，删除后保留一条「已关闭」的记录，否则会自动重新出现。
    """
    code = code.upper()
    if code == "GLOBAL":
        raise APIError(409, "NO_CHANGE", "国际频道各国共享，不能删除")
    row = session.get(Region, code)
    name = row.name_hans if row else DEFAULT_REGIONS.get(code, ("", ""))[0]
    if row is None and code not in DEFAULT_REGIONS:
        raise APIError(404, "REGION_NOT_FOUND", "没有这个国家")
    if body.confirm_name.strip() != name:
        raise APIError(422, "VALIDATION_FAILED", "输入的国家名不一致，没有删除")
    # 先删房间再删频道：频道删除时会给下属房间解除归属，房间先没了就不用改
    channels = session.scalars(
        select(Channel).where(Channel.region_code == code).order_by((Channel.kind == "room").desc())
    ).all()
    removed_posts = 0
    orphaned: list[str] = []
    for channel in channels:
        posts, files = _purge_channel(session, channel)
        removed_posts += posts
        orphaned += files
    session.execute(
        update(UserRegionPref).where(UserRegionPref.region_code == code).values(region_code="GLOBAL", browse_region_code=None)
    )
    session.execute(update(UserRegionPref).where(UserRegionPref.browse_region_code == code).values(browse_region_code=None))
    session.execute(delete(RegionOpenRequest).where(RegionOpenRequest.region_code == code))
    if code in DEFAULT_REGIONS:
        _region_row(session, code).is_open = False
    elif row is not None:
        session.delete(row)
    detail = f"{name}（{code}），连同 {len(channels)} 个频道 / 房间、{removed_posts} 条内容"
    detail += f"：{body.note}" if body.note else ""
    write_audit(session, admin.id, "admin.region.delete", "region", code, detail[:300])
    session.commit()
    return {
        "deleted": True,
        "removed_channels": len(channels),
        "removed_posts": removed_posts,
        "files_left": _delete_files(orphaned),
    }


@router.post("/regions/{code}/channels")
def fill_region_channels(
    code: str,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """给已开通的国家（或国际）补齐默认频道；已有同分类官方频道的不重复建。"""
    code = code.upper()
    regions = open_regions(session)
    if code not in regions:
        raise APIError(404, "REGION_NOT_FOUND", "这个国家还没开通")
    created = ensure_region_channels(session, code, regions[code][0])
    if created:
        write_audit(session, admin.id, "admin.region.fill", "region", code)
    session.commit()
    return {"code": code, "channels": [channel.name_hans for channel in created]}

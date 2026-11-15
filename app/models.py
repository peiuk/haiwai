import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(40))
    handle: Mapped[str | None] = mapped_column(String(20), unique=True)
    avatar_tone: Mapped[str] = mapped_column(String(1), default="a")
    avatar_key: Mapped[str | None] = mapped_column(String(32))  # 上传的头像图片；为空时显示首字色块
    city_label: Mapped[str | None] = mapped_column(String(12))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    script_pref: Mapped[str] = mapped_column(String(8), default="hans")
    status: Mapped[str] = mapped_column(String(16), default="active")
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # 管理员：可以审核内容、处理举报。设置方式见 app/make_admin.py。
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # 超级管理员：在管理员之上，还能彻底删除、管理频道和国家、任免管理员、导出数据。
    is_super: Mapped[bool] = mapped_column(Boolean, default=False)
    # 后台两步验证的密钥（base32）；为空表示没开。
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    # 限时封禁的到期时间；为空且 status=suspended 表示永久。到期后下次登录自动解封。
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspend_reason: Mapped[str | None] = mapped_column(String(300))  # 登录被拒时告诉本人
    dm_allow_strangers: Mapped[bool] = mapped_column(Boolean, default=True)
    feed_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Channel(Base):
    __tablename__ = "channel"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(48), unique=True)
    name_hans: Mapped[str] = mapped_column(String(64))
    name_hant: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    room_type: Mapped[str] = mapped_column(String(16), default="general")
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    region_code: Mapped[str] = mapped_column(String(16), default="UK")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    parent_channel_id: Mapped[str | None] = mapped_column(String(36))
    review_status: Mapped[str] = mapped_column(String(16), default="approved")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    # 同一国家内的排列顺序，小的在前；0 表示没指定（排最前，按代号排）。
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # 后台给用户房间 / 频道加的认证；官方频道（kind 以 official 开头）天然认证，见 certified。
    is_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String(16))
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    cover_key: Mapped[str | None] = mapped_column(String(64))  # 房间封面图（剧集房间页顶部），房主上传
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def certified(self) -> bool:
        return (self.kind or "").startswith("official") or bool(self.is_certified)


class Region(Base):
    """后台开通的国家。英国和国际内置在 app/core/regions.py，这里有同代码记录时以这里为准。"""

    __tablename__ = "region"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name_hans: Mapped[str] = mapped_column(String(32))
    city: Mapped[str] = mapped_column(String(32), default="")  # 分站城市，漫游提示用
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChannelSubscription(Base):
    __tablename__ = "channel_subscription"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventCluster(Base):
    __tablename__ = "event_cluster"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Content(Base):
    __tablename__ = "content"
    __table_args__ = (
        CheckConstraint("type <> 'news' OR canonical_url IS NOT NULL", name="chk_news_link"),
        CheckConstraint("type <> 'listing' OR expires_at IS NOT NULL", name="chk_listing_expiry"),
        Index("ix_content_status_created", "status", "created_at"),  # 后台列表、审核队列
        Index("ix_content_author", "author_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    author_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    repost_of_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200))
    title_hant: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(String(500))
    summary_hant: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    city_topic: Mapped[str | None] = mapped_column(String(12))
    keyword_source: Mapped[str | None] = mapped_column(String(16))
    canonical_url: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(96))
    licence_ref: Mapped[str | None] = mapped_column(Text)
    image_key: Mapped[str | None] = mapped_column(String(64))
    # 分类信息多图（最多 4 张，JSON 数组）。image_key 保留为首图，供旧消费方兼容。
    image_keys_json: Mapped[str] = mapped_column(Text, default="[]")
    video_key: Mapped[str | None] = mapped_column(String(64))
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    embed_provider_code: Mapped[str | None] = mapped_column(String(32))
    embed_media_id: Mapped[str | None] = mapped_column(String(32))
    embed_source_url: Mapped[str | None] = mapped_column(Text)
    embed_status: Mapped[str] = mapped_column(String(16), default="none")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    ai_status: Mapped[str] = mapped_column(String(16), default="pending")
    event_cluster_id: Mapped[str | None] = mapped_column(String(36))
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    # 后台设为精选的时间；为空表示不是精选。精选内容在「为你推荐」里加权。
    featured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelItem(Base):
    __tablename__ = "channel_item"
    __table_args__ = (Index("ix_channel_item_content", "content_id"),)  # 主键以 channel_id 开头，按内容反查要单独的索引

    channel_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    origin_room_id: Mapped[str | None] = mapped_column(String(36))
    sort_key: Mapped[str] = mapped_column(String(16), default="")
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    season: Mapped[int | None] = mapped_column(Integer)
    episode: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    channel: Mapped[Channel] = relationship()
    content: Mapped[Content] = relationship()


class ChannelCollaborator(Base):
    __tablename__ = "channel_collaborator"

    channel_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserItemProgress(Base):
    __tablename__ = "user_item_progress"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    watch_mark: Mapped[str] = mapped_column(String(16), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConsentRecord(Base):
    __tablename__ = "consent_record"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(48))
    version: Mapped[str] = mapped_column(String(32))
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModerationCase(Base):
    __tablename__ = "moderation_case"
    __table_args__ = (Index("ix_case_status_created", "status", "created_at"), Index("ix_case_content", "content_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content_id: Mapped[str | None] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"))
    reported_user_id: Mapped[str | None] = mapped_column(String(36))
    reported_channel_id: Mapped[str | None] = mapped_column(String(36))
    reported_comment_id: Mapped[str | None] = mapped_column(String(36))
    reporter_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    reason: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(16), default="open")
    decision: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(String(200))
    content_id: Mapped[str | None] = mapped_column(String(36))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserRegionPref(Base):
    __tablename__ = "user_region_pref"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    region_code: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    browse_region_code: Mapped[str | None] = mapped_column(String(16))
    consent_id: Mapped[str | None] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegionOpenRequest(Base):
    __tablename__ = "region_open_request"
    __table_args__ = (UniqueConstraint("user_id", "region_code", name="uq_region_open"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    region_code: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshSession(Base):
    __tablename__ = "refresh_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # 后台登录（过了两步验证）发的会话：有效期短，续期后仍是后台会话。
    admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PasswordReset(Base):
    """一次性的重置密码凭证。库里只存哈希；用过或过期就失效。"""

    __tablename__ = "password_reset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ListingExt(Base):
    __tablename__ = "listing_ext"

    content_id: Mapped[str] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    area: Mapped[str] = mapped_column(String(80))
    price_amount: Mapped[str] = mapped_column(String(32))
    price_unit: Mapped[str | None] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(8))
    contact: Mapped[str] = mapped_column(String(120))
    attrs_json: Mapped[str] = mapped_column(Text, default="{}")
    closed_reason: Mapped[str | None] = mapped_column(String(16))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContactView(Base):
    __tablename__ = "contact_view"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    content_id: Mapped[str] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"))
    viewed_on: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContentReaction(Base):
    __tablename__ = "content_reaction"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    liked: Mapped[bool] = mapped_column(Boolean, default=False)
    favorited: Mapped[bool] = mapped_column(Boolean, default=False)


class RoomPostPush(Base):
    __tablename__ = "room_post_push"

    content_id: Mapped[str] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"))
    channel_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"))
    pushed_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserFollow(Base):
    __tablename__ = "user_follow"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserBlock(Base):
    __tablename__ = "user_block"

    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DmThread(Base):
    __tablename__ = "dm_thread"
    __table_args__ = (UniqueConstraint("user_low", "user_high", name="uq_dm_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_low: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    user_high: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="request")
    listing_inquiry: Mapped[bool] = mapped_column(Boolean, default=False)
    listing_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DmMessage(Base):
    __tablename__ = "dm_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    thread_id: Mapped[str] = mapped_column(ForeignKey("dm_thread.id", ondelete="CASCADE"))
    sender_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    kind: Mapped[str] = mapped_column(String(16), default="text")
    body: Mapped[str] = mapped_column(String(1000))
    image_key: Mapped[str | None] = mapped_column(String(64))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoomComment(Base):
    __tablename__ = "room_comment"
    __table_args__ = (Index("ix_comment_status_created", "status", "created_at"), Index("ix_comment_content", "content_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"))
    content_id: Mapped[str | None] = mapped_column(String(36))
    parent_id: Mapped[str | None] = mapped_column(String(36))
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(1000))
    image_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    keyword_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommentLike(Base):
    __tablename__ = "comment_like"

    comment_id: Mapped[str] = mapped_column(ForeignKey("room_comment.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoomJoinRequest(Base):
    __tablename__ = "room_join_request"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_join"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoomBan(Base):
    """房主移出房间并禁止再加入的人。"""

    __tablename__ = "room_ban"

    room_id: Mapped[str] = mapped_column(ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserConsentLog(Base):
    __tablename__ = "user_consent_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    provider_code: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(16))
    policy_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UploadObject(Base):
    __tablename__ = "upload_object"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    content_type: Mapped[str] = mapped_column(String(64))
    stored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_created", "created_at"), Index("ix_audit_target", "target_type", "target_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str | None] = mapped_column(String(24))
    target_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[str | None] = mapped_column(String(300))  # 操作理由 / 备注
    ip: Mapped[str | None] = mapped_column(String(64))  # 操作来源，账号被盗时用来分辨是不是本人
    user_agent: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewClaim(Base):
    """审核认领：谁正在处理队列里的哪一条，免得两个管理员同时审同一条。10 分钟不处理自动失效。"""

    __tablename__ = "review_claim"

    target_type: Mapped[str] = mapped_column(String(16), primary_key=True)  # content / comment / channel / case
    target_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admin_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SiteSetting(Base):
    """全站开关，后台改。目前只有 review.post / review.listing / review.comment（on / off，没有记录等于 on）。"""

    __tablename__ = "site_setting"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BlockedTerm(Base):
    """敏感词 / 链接黑名单：标题、正文、留言里出现任意一条，就先进待审核而不是直接发布。"""

    __tablename__ = "blocked_term"

    term: Mapped[str] = mapped_column(String(64), primary_key=True)  # 小写保存，匹配时不分大小写
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

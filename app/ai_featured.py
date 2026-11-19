"""AI 精选：每天从最近 48 小时发布的公开用户帖子和分类信息里，让 AI 挑最多 5 条设为精选，7 天后自动取消。

人工在后台设的精选不过期；AI 设的在后台标「AI 精选」，管理员随时可以取消，取消过的不会再被 AI 选上。
随每日资讯任务一起跑（app/news.py 的 run_once）；`python -m app.ai_featured` 立刻跑一次。
用户内容会发给 .env 里配置的 AI（LLM_API_BASE / LLM_API_KEY / LLM_MODEL），和每日资讯同一套。
"""
from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.feed import image_keys_of
from app.llm import LLMUnavailable, ask_json
from app.models import AuditLog, Channel, ChannelItem, Content, User, utcnow

MAX_PICKS = 5
CANDIDATES = 60
WINDOW = timedelta(hours=48)
KEEP = timedelta(days=7)
PICK_ACTION = "ai.content.feature"

SYSTEM = f"""你是英国华人社区 App「海外圈」的编辑。下面是最近用户发的帖子和分类信息（编号、类型、标题、内容、有几张图）。
挑出最多 {MAX_PICKS} 条值得放进「精选」推荐给所有人的：内容完整、对在英 / 海外华人有实际用处或有意思、像真人分享。
不要选：广告引流、留联系方式拉人、重复刷屏、低俗、引战、只有一两句话没信息量的。没有合适的就少选或一条都不选。
reason 用一句中文说明为什么选。"""
JSON_SHAPE = '\n只输出一个 JSON 对象，不要任何其他文字，格式：{"items":[{"index":0,"reason":"…"}]}。'


class Pick(BaseModel):
    index: int
    reason: str


class Picks(BaseModel):
    items: list[Pick]


def expire_ai_featured(session: Session) -> int:
    """AI 设的精选到期就取消。人工设的（ai_featured_until 为空）不动。"""
    result = session.execute(
        update(Content)
        .where(Content.ai_featured_until.is_not(None), Content.ai_featured_until <= utcnow())
        .values(featured_at=None, ai_featured_until=None)
    )
    session.commit()
    return result.rowcount or 0


def candidates(session: Session) -> list[Content]:
    in_public_channel = (
        select(ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(Channel.is_active.is_(True), ~((Channel.kind == "room") & Channel.is_private.is_(True)))
    )
    in_private_room = (
        select(ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(Channel.kind == "room", Channel.is_private.is_(True))
    )
    picked_before = select(AuditLog.target_id).where(AuditLog.action == PICK_ACTION)  # 管理员取消过的不再选
    return list(
        session.scalars(
            select(Content)
            .join(User, User.id == Content.author_id)
            .where(
                Content.status == "published",
                Content.deleted_at.is_(None),
                Content.featured_at.is_(None),
                Content.type != "repost",
                Content.created_at >= utcnow() - WINDOW,
                User.status == "active",
                User.deleted_at.is_(None),
                Content.id.in_(in_public_channel),
                Content.id.not_in(in_private_room),
                Content.id.not_in(picked_before),
            )
            .order_by(Content.created_at.desc())
            .limit(CANDIDATES)
        ).all()
    )


def ask_ai(listing: str) -> list[Pick]:
    return ask_json(SYSTEM, listing, Picks, JSON_SHAPE).items


def _describe(index: int, content: Content) -> str:
    kind = "分类信息" if content.type == "listing" else "帖子"
    text = (content.body or content.summary or "").strip().replace("\n", " ")[:300]
    return f"[{index}] {kind} · {len(image_keys_of(content))} 张图\n标题：{content.title}\n内容：{text}"


def run_ai_featured(session: Session, ask=None) -> dict[str, int]:
    expired = expire_ai_featured(session)  # 先取消到期的；后面 AI 出错也不影响
    pool = candidates(session)
    if not pool:
        return {"expired": expired, "candidates": 0, "picked": 0}
    picks = (ask or ask_ai)("\n\n".join(_describe(i, c) for i, c in enumerate(pool)))
    now = utcnow()
    chosen: set[int] = set()
    for pick in picks:
        # 编号越界、重复的不要；最多 MAX_PICKS 条，AI 多给了也只取前面的
        if not 0 <= pick.index < len(pool) or pick.index in chosen or len(chosen) >= MAX_PICKS:
            continue
        chosen.add(pick.index)
        content = pool[pick.index]
        content.featured_at = now
        content.ai_featured_until = now + KEEP
        write_audit(session, None, PICK_ACTION, "content", content.id, pick.reason[:300])
    session.commit()
    return {"expired": expired, "candidates": len(pool), "picked": len(chosen)}


if __name__ == "__main__":
    from app.core.db import get_db

    db = next(get_db())
    try:
        print(run_ai_featured(db))
    except LLMUnavailable as err:
        print(f"AI 精选没有运行：{err}")
        raise SystemExit(1)
    finally:
        db.close()

"""发帖 / 改帖后让 AI 补关键词、看频道放没放对。接口不等它：在后台跑，出错就保持原样（词表补的那几个关键词）。

关键词：用户自己填的不动，只替换系统自动补的（keyword_source 不是 user）；存在关键词那一栏，不改正文。
频道：只看发在官方频道里的普通帖子（分类信息的分类和频道绑定，房间归房主管，都不看）。AI 觉得放错了，
只记下建议和理由，后台管理员点「移过去」才移，并通知作者（见 admin.decide_ai_channel）。
用户内容会发给 .env 里配置的 AI，和每日资讯同一套；没配密钥时什么都不做。
"""
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.regions import region_name
from app.keywords import collect_keywords, dump_keywords
from app.llm import LLMUnavailable, ask_json
from app.models import Channel, ChannelItem, Content

NEWS_CATEGORIES = {"资讯", "新闻"}  # 资讯频道放官方稿子，不建议用户帖子移进去
MAX_TEXT = 1500

SYSTEM = """你是海外华人社区 App「海外圈」的编辑助手。下面是一条用户刚发的帖子。
1. keywords：给它配 1～5 个中文关键词，方便别人搜索：地名（城市、地区，用常见中文译名）、国家、事情类型（如租房、找工作、签证、二手、美食）。
   每个 1～12 个字，不带 #，不要空格，不要重复「城市话题」里已有的词；内容太少看不出来就少给或不给。
2. channel_index：如果给了「可选频道」，选这条帖子最该放的频道编号；现在的频道就合适时填现在频道的编号。拿不准就填现在的。
3. reason：如果建议换频道，用一句中文说明为什么；不换就留空。"""
JSON_SHAPE = '\n只输出一个 JSON 对象，不要任何其他文字，格式：{"keywords":["…"],"channel_index":0,"reason":""}。'


class Verdict(BaseModel):
    keywords: list[str] = []
    channel_index: int = -1
    reason: str = ""


def ask_ai(prompt: str) -> Verdict:
    return ask_json(SYSTEM, prompt, Verdict, JSON_SHAPE)


def _home_channel(session: Session, content: Content) -> Channel | None:
    # 房间推到频道的那条（origin_room_id 不为空）不算：帖子的家还是房间
    return session.scalar(
        select(Channel)
        .join(ChannelItem, ChannelItem.channel_id == Channel.id)
        .where(ChannelItem.content_id == content.id, ChannelItem.origin_room_id.is_(None))
        .limit(1)
    )


def channel_options(session: Session, content: Content) -> tuple[Channel | None, list[Channel]]:
    """返回（现在的频道, 可选频道）。不该看频道的帖子，可选频道为空。"""
    current = _home_channel(session, content)
    if (
        content.type == "listing"
        or current is None
        or not (current.kind or "").startswith("official")
        or current.category in NEWS_CATEGORIES
    ):
        return current, []
    options = session.scalars(
        select(Channel)
        .where(
            Channel.kind.like("official%"),
            Channel.is_active.is_(True),
            Channel.region_code == current.region_code,
            Channel.category.not_in(NEWS_CATEGORIES),
        )
        .order_by(Channel.sort_order, Channel.code)
    ).all()
    return current, list(options)


def _prompt(session: Session, content: Content, current: Channel | None, options: list[Channel]) -> str:
    text = (content.body or content.summary or "").strip()[:MAX_TEXT]
    lines = [f"标题：{content.title}", f"正文：{text}", f"城市话题：{content.city_topic or '无'}"]
    if current is not None:
        lines.append(f"国家 / 地区：{region_name(session, current.region_code)}")
    if options:
        lines.append("可选频道：")
        lines += [f"[{i}] {c.name_hans}{'（现在的频道）' if c.id == current.id else ''}" for i, c in enumerate(options)]
    return "\n".join(lines)


def tag_content(session: Session, content_id: str, ask=None) -> None:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None:
        return
    current, options = channel_options(session, content)
    if content.keyword_source == "user" and not options:
        return
    verdict = (ask or ask_ai)(_prompt(session, content, current, options))
    session.refresh(content)  # AI 想了几十秒，这期间作者可能改过帖子
    if content.deleted_at is not None:
        return
    if content.keyword_source != "user":
        words = [w for w in collect_keywords(verdict.keywords, "") if w != content.city_topic]
        if words:
            content.keywords_json = dump_keywords(words)
            content.keyword_source = "ai_auto"
    if options and current is not None and 0 <= verdict.channel_index < len(options):
        target = options[verdict.channel_index]
        moved = target.id != current.id  # 改帖后又放对了：清掉之前的建议
        content.ai_channel_id = target.id if moved else None
        content.ai_channel_reason = (verdict.reason.strip()[:200] or None) if moved else None
    session.commit()


def tag_in_background(bind: Engine | Connection, content_id: str) -> None:
    """发帖接口的后台任务：请求的数据库会话已经关了，另开一个。出错只打日志，帖子保持原样。"""
    with Session(bind=bind) as session:
        try:
            tag_content(session, content_id)
        except LLMUnavailable:
            session.rollback()  # 没配密钥 / AI 暂时不可用：关键词用词表补的就行
        except Exception as err:
            session.rollback()
            print(f"AI 关键词出错（{content_id}）：{err!r}", flush=True)

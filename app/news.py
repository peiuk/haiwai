"""每日 AI 资讯：抓 GOV.UK 和 BBC 最新新闻 → AI 写中文标题和摘要 → 存为待审，管理员在「待审核」里一键发布。

英国的（签证政策、重大新闻）进「英国资讯」，国际新闻和海外华人相关的进「国际新闻」。
GOV.UK 是 Open Government Licence v3.0（允许翻译改编，须署名并附原文链接）；BBC 有版权，
中文摘要由运营方决定使用、自担风险（2026-11-19 确认）。都只存 AI 写的标题摘要和原文链接，不存全文。
用法：后台「待审核」页的「抓取今日资讯」按钮；`python -m app.news` 立刻跑一次；
`python -m app.news --daily` 常驻、每天伦敦时间 8 点自动跑（docker compose 的 news 服务）。
"""
import hashlib
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import LLMUnavailable, ask_json
from app.models import Channel, ChannelItem, Content, utcnow

GOVUK_SEARCH = "https://www.gov.uk/api/search.json"
SOURCE = "GOV.UK"
LICENCE = "OGL v3.0"
BBC = "BBC"
BBC_LICENCE = "© BBC"
# 英国新闻和国际新闻两个源；后面的字给 AI 当提示，最后归哪个频道由 AI 判断
BBC_FEEDS = (
    ("https://feeds.bbci.co.uk/news/uk/rss.xml", "英国"),
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "国际"),
)
MAX_ITEMS = 20  # 每个源最多取这么多条

SYSTEM = """你是华人社区 App「海外圈」的资讯编辑。下面是 GOV.UK 和 BBC 刚发布的新闻（来源、标题和简介，英文）。
为每一条写：
- title_zh：简体中文标题，不超过 30 个字。
- summary_zh：简体中文摘要，不超过 120 个字，说清发生了什么、谁受影响。
- scope：英国本地的新闻为 "uk"；英国以外的国际新闻为 "international"。
- relevant：
  · scope 为 uk 时，对在英华人有实际影响（签证移民政策、租房、医疗、税务、教育、交通、工作、治安、物价、福利等）
    或是全英国关注的重大新闻时为 true；部门人事、外交礼节、只涉及个别地方或行业内部、体育娱乐八卦为 false。
  · scope 为 international 时，重大国际新闻，或和中国、华人、海外华人有关的新闻为 true；其余为 false。
硬性要求：只能使用给出的信息，不得添加原文没有的事实、数字、日期或建议；信息不够就写得更概括，宁可少写。"""

Scope = Literal["uk", "international"]


class Draft(BaseModel):
    index: int
    title_zh: str  # 不设长度上限：一条写长了不该让整批作废，保存时会截断
    summary_zh: str
    relevant: bool
    scope: Scope


class Drafts(BaseModel):
    items: list[Draft]


class NewsUnavailable(Exception):
    """没配 AI 密钥、AI 调用失败或来源全都打不开：这次什么都不写，下次再跑。"""


def fetch_govuk(limit: int = MAX_ITEMS) -> list[dict[str, str]]:
    try:
        response = httpx.get(
            GOVUK_SEARCH,
            params={
                "filter_content_store_document_type": ["news_story", "press_release"],
                "order": "-public_timestamp",
                "count": limit,
                "fields": "title,link,description,public_timestamp",
            },
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPError as err:
        raise NewsUnavailable(f"GOV.UK 暂时打不开：{err}") from err
    return [
        {
            "title": row.get("title") or "",
            "description": row.get("description") or "",
            "url": f"https://www.gov.uk{row['link']}",
            "published": row.get("public_timestamp") or "",
            "source": SOURCE,
            "licence": LICENCE,
            "hint": "英国",
        }
        for row in response.json().get("results", [])
        if row.get("link") and row.get("title")
    ]


def fetch_bbc(limit: int = MAX_ITEMS) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for feed, hint in BBC_FEEDS:
        try:
            response = httpx.get(feed, timeout=20, follow_redirects=True)
            response.raise_for_status()
            channel = ET.fromstring(response.content).find("channel")
        except (httpx.HTTPError, ET.ParseError) as err:
            raise NewsUnavailable(f"BBC 暂时打不开：{err}") from err
        for row in (channel.findall("item") if channel is not None else [])[:limit]:
            title, link = (row.findtext("title") or "").strip(), (row.findtext("link") or "").strip()
            if not title or not link:
                continue
            try:
                published = parsedate_to_datetime(row.findtext("pubDate") or "").isoformat()
            except (TypeError, ValueError):
                published = ""
            items.append({
                "title": title,
                "description": (row.findtext("description") or "").strip(),
                # 去掉 ?at_medium=RSS 这类追踪参数：同一篇在两个源里链接不一样，去重靠链接
                "url": link.split("?")[0],
                "published": published,
                "source": BBC,
                "licence": BBC_LICENCE,
                "hint": hint,
            })
    return items


def fetch_all() -> list[dict[str, str]]:
    """各个源分开抓：一个打不开就跳过、记一笔，不连累其他源；全都打不开才算这次没有。"""
    items: list[dict[str, str]] = []
    failures: list[str] = []
    for fetch in (fetch_govuk, fetch_bbc):
        try:
            items.extend(fetch())
        except NewsUnavailable as err:
            failures.append(str(err))
            print(f"{utcnow().isoformat()} 资讯来源跳过：{err}", flush=True)
    if failures and not items:
        raise NewsUnavailable("；".join(failures))
    return items


JSON_SHAPE = (
    '\n只输出一个 JSON 对象，不要任何其他文字，格式：{"items":[{"index":0,"title_zh":"…","summary_zh":"…",'
    '"relevant":true,"scope":"uk"}]}。每条输入都要有一项；scope 只能是 uk 或 international。'
)


def write_drafts(items: list[dict[str, str]]) -> list[Draft]:
    listing = "\n\n".join(
        f"[{i}] 来源：{item['source']}（{item['hint']}）\n{item['title']}\n{item['description']}" for i, item in enumerate(items)
    )
    try:
        return ask_json(SYSTEM, listing, Drafts, JSON_SHAPE).items
    except LLMUnavailable as err:
        raise NewsUnavailable(str(err)) from err


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_match(source: str, written: str) -> bool:
    """中文稿里的每个数字都要在原文里出现过；对不上就标「待核对」，提醒审核时看原文。"""
    plain = source.replace(",", "")
    return all(number in plain for number in _NUMBER.findall(written.replace(",", "")))


# 频道代号；后台改过代号就退回按国家 + 分类找同类官方频道
_SCOPE_CHANNELS = {"uk": ("uk-news", "UK", "资讯"), "international": ("global-news", "GLOBAL", "新闻")}


def _news_channel(session: Session, scope: Scope) -> Channel | None:
    code, region, category = _SCOPE_CHANNELS[scope]
    channel = session.scalar(select(Channel).where(Channel.code == code, Channel.is_active.is_(True)))
    return channel or session.scalar(
        select(Channel).where(
            Channel.region_code == region,
            Channel.category == category,
            Channel.kind.like("official%"),
            Channel.is_active.is_(True),
        )
    )


DIGEST_PREFIX = "今日英国要闻"


def publish_digest(session: Session) -> int:
    """把上一篇要闻之后（或最近 24 小时内）管理员已通过的资讯汇成一篇「今日英国要闻」，直接发布。

    只收已发布的 GOV.UK 稿子（BBC 的有版权，不再汇编转载）：被拒绝的不会出现；内容都经过人工审核，汇总帖本身不再待审。一天只发一篇。
    """
    channel = _news_channel(session, "uk")
    if channel is None:
        return 0
    now = utcnow()
    title = f"{DIGEST_PREFIX} · {now.month}月{now.day}日"
    previous = session.scalar(
        select(Content)
        .where(Content.type == "post", Content.source_name == SOURCE, Content.title.startswith(DIGEST_PREFIX))
        .order_by(Content.created_at.desc())
        .limit(1)
    )
    if previous is not None and previous.title == title:
        return 0
    since = previous.created_at if previous is not None else now - timedelta(hours=24)
    approved = session.scalars(
        select(Content)
        .where(
            Content.type == "news",
            Content.source_name == SOURCE,
            Content.status == "published",
            Content.deleted_at.is_(None),
            Content.published_at > since,
        )
        .order_by(Content.published_at)
    ).all()
    if not approved:
        return 0
    lines = [f"{n}. {c.title}\n{c.summary}\n原文：{c.canonical_url}" for n, c in enumerate(approved, start=1)]
    lines.append("本文由 AI 根据 GOV.UK 公开信息（Open Government Licence v3.0）整理成中文，各条均经编辑审核；一切以原文为准。")
    digest = Content(
        type="post",
        status="published",
        title=title,
        summary="；".join(c.title for c in approved[:3])[:200],
        body="\n\n".join(lines),
        source_name=SOURCE,
        licence_ref=LICENCE,
        published_at=now,
        ai_status="ok",
    )
    session.add(digest)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=digest.id))
    session.commit()
    return 1


def run_daily_news(session: Session, fetch=None, write=None) -> dict[str, int]:
    fetch = fetch or fetch_all
    write = write or write_drafts
    digest = publish_digest(session)  # 先汇总已通过的，再抓新的；后面 AI 出错也不影响这一篇
    since = utcnow() - timedelta(hours=36)
    fresh: list[dict[str, str]] = []
    for item in fetch():
        url_hash = hashlib.sha256(item["url"].strip().lower().encode()).hexdigest()
        published = _parse_time(item["published"])
        # shortcut: 判为不相关的不落库，36 小时内重跑会再让 AI 判一次；量大或费用敏感时再记下已判过的链接。
        if published and published < since:
            continue
        if session.scalar(select(Content.id).where(Content.content_hash == url_hash)) is not None:
            continue
        fresh.append({**item, "hash": url_hash})
    if not fresh:
        return {"fetched": 0, "drafted": 0, "skipped": 0, "to_check": 0, "digest": digest}

    written = write(fresh)
    # 每条输入必须恰好对应一条稿子；编号漏了或重了，摘要就可能配到别的文章的链接上，整批作废
    if sorted(draft.index for draft in written) != list(range(len(fresh))):
        raise NewsUnavailable("AI 返回的条目和输入对不上，这次不生成")
    drafts = {draft.index: draft for draft in written}
    created: list[Content] = []
    to_check = 0
    for index, item in enumerate(fresh):
        draft = drafts.get(index)
        if draft is None or not draft.relevant:
            continue
        channel = _news_channel(session, draft.scope)
        if channel is None:
            continue
        verified = numbers_match(f"{item['title']} {item['description']}", f"{draft.title_zh} {draft.summary_zh}")
        to_check += 0 if verified else 1
        content = Content(
            type="news",
            status="pending",
            title=draft.title_zh[:200],
            summary=draft.summary_zh[:200],
            canonical_url=item["url"],
            source_name=item["source"],
            licence_ref=item["licence"],
            content_hash=item["hash"],
            ai_status="ok" if verified else "check",
        )
        session.add(content)
        session.flush()
        session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
        created.append(content)
    session.commit()
    return {
        "fetched": len(fresh),
        "drafted": len(created),
        "skipped": len(fresh) - len(created),
        "to_check": to_check,
        "digest": digest,
    }


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


LONDON = ZoneInfo("Europe/London")
RUN_HOUR = 8  # 每天伦敦时间 8 点


def seconds_until_next_run(now: datetime) -> float:
    local = now.astimezone(LONDON)
    target = local.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    if target <= local:
        target = (local + timedelta(days=1)).replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    # 换成 UTC 再相减：同一时区的两个时间直接相减会忽略中间的冬夏令时切换，改时那天差一小时
    return (target.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds()


def run_once() -> int:
    from app.core.db import get_db

    from app.housekeeping import run_housekeeping

    db = next(get_db())
    try:
        # 顺带做每日清理（没用上的上传文件、过期限流记录）；清理失败不影响资讯
        try:
            print(f"{utcnow().isoformat()} 每日清理：{run_housekeeping(db)}", flush=True)
        except Exception as err:
            db.rollback()
            print(f"{utcnow().isoformat()} 每日清理出错：{err!r}", flush=True)
        print(f"{utcnow().isoformat()} 每日资讯：{run_daily_news(db)}", flush=True)
        return 0
    except NewsUnavailable as err:
        print(f"{utcnow().isoformat()} 每日资讯没有生成：{err}", flush=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    # 不带参数：立刻跑一次（给系统定时任务用）。--daily：常驻，每天 8 点跑（给 docker compose 的 news 服务用，只开一个进程，避免重复调用 AI）。
    if "--daily" not in sys.argv:
        raise SystemExit(run_once())
    while True:
        time.sleep(seconds_until_next_run(utcnow()))
        try:
            run_once()
        except Exception as err:  # 某天出错不能让常驻进程退出，第二天照常跑
            print(f"{utcnow().isoformat()} 每日资讯出错：{err!r}", flush=True)

"""每日 AI 资讯：抓 GOV.UK 最新新闻 → AI 写中文标题和摘要 → 存为待审，管理员在「待审核」里一键发布。

只用 GOV.UK（Open Government Licence v3.0，允许翻译改编，须署名并附原文链接）；不存全文。
用法：后台「待审核」页的「抓取今日资讯」按钮；`python -m app.news` 立刻跑一次；
`python -m app.news --daily` 常驻、每天伦敦时间 8 点自动跑（docker compose 的 news 服务）。
"""
import hashlib
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import anthropic
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Channel, ChannelItem, Content, utcnow

GOVUK_SEARCH = "https://www.gov.uk/api/search.json"
SOURCE = "GOV.UK"
LICENCE = "OGL v3.0"
MAX_ITEMS = 20

SYSTEM = """你是英国华人社区 App「海外圈」的资讯编辑。下面是 GOV.UK 刚发布的新闻（标题和简介，英文）。
为每一条写：
- title_zh：简体中文标题，不超过 30 个字。
- summary_zh：简体中文摘要，不超过 120 个字，说清发生了什么、谁受影响。
- relevant：对在英华人的日常生活有实际影响时为 true（签证移民、租房、医疗、税务、教育、交通、工作、治安、物价、福利等）；
  部门人事、外交礼节、只涉及个别地方或行业内部的消息为 false。
- topic：从给定选项里选最贴近的一个。
硬性要求：只能使用给出的信息，不得添加原文没有的事实、数字、日期或建议；信息不够就写得更概括，宁可少写。"""

Topic = Literal["签证移民", "租房住房", "医疗健康", "税务财务", "教育", "交通出行", "工作就业", "其他"]


class Draft(BaseModel):
    index: int
    title_zh: str = Field(max_length=60)
    summary_zh: str = Field(max_length=240)
    relevant: bool
    topic: Topic


class Drafts(BaseModel):
    items: list[Draft]


class NewsUnavailable(Exception):
    """没配 AI 密钥、AI 调用失败或来源打不开：这次什么都不写，下次再跑。"""


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
        }
        for row in response.json().get("results", [])
        if row.get("link") and row.get("title")
    ]


def write_drafts(items: list[dict[str, str]]) -> list[Draft]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise NewsUnavailable("还没有配置 AI 密钥（.env 里的 LLM_API_KEY）")
    listing = "\n\n".join(f"[{i}] {item['title']}\n{item['description']}" for i, item in enumerate(items))
    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    try:
        response = client.beta.messages.parse(
            model=settings.news_model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # 主模型拒答时由服务端换模型重试
            system=SYSTEM,
            messages=[{"role": "user", "content": listing}],
            output_format=Drafts,
        )
    except anthropic.APIError as err:
        raise NewsUnavailable(f"AI 调用失败：{err}") from err
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise NewsUnavailable("AI 没有给出结果")
    return response.parsed_output.items


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_match(source: str, written: str) -> bool:
    """中文稿里的每个数字都要在原文里出现过；对不上就标「待核对」，提醒审核时看原文。"""
    plain = source.replace(",", "")
    return all(number in plain for number in _NUMBER.findall(written.replace(",", "")))


def _uk_channel(session: Session, codes: tuple[str, ...]) -> Channel | None:
    for code in codes:
        channel = session.scalar(select(Channel).where(Channel.code == code, Channel.is_active.is_(True)))
        if channel is not None:
            return channel
    return session.scalar(
        select(Channel).where(
            Channel.region_code == "UK",
            Channel.category == "资讯",
            Channel.kind.like("official%"),
            Channel.is_active.is_(True),
        )
    )


_TOPIC_CHANNELS = {"签证移民": ("uk-visa",), "租房住房": ("uk-housing",)}


def run_daily_news(session: Session, fetch=None, write=None) -> dict[str, int]:
    fetch = fetch or fetch_govuk
    write = write or write_drafts
    since = utcnow() - timedelta(hours=36)
    fresh: list[dict[str, str]] = []
    for item in fetch():
        digest = hashlib.sha256(item["url"].strip().lower().encode()).hexdigest()
        published = _parse_time(item["published"])
        # shortcut: 判为不相关的不落库，36 小时内重跑会再让 AI 判一次；量大或费用敏感时再记下已判过的链接。
        if published and published < since:
            continue
        if session.scalar(select(Content.id).where(Content.content_hash == digest)) is not None:
            continue
        fresh.append({**item, "hash": digest})
    if not fresh:
        return {"fetched": 0, "drafted": 0, "skipped": 0, "to_check": 0}

    drafts = {draft.index: draft for draft in write(fresh)}
    news_channel = _uk_channel(session, ())
    created: list[tuple[Content, dict[str, str]]] = []
    to_check = 0
    for index, item in enumerate(fresh):
        draft = drafts.get(index)
        if draft is None or not draft.relevant:
            continue
        channel = _uk_channel(session, _TOPIC_CHANNELS.get(draft.topic, ()))
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
            source_name=SOURCE,
            licence_ref=LICENCE,
            content_hash=item["hash"],
            ai_status="ok" if verified else "check",
        )
        session.add(content)
        session.flush()
        session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
        created.append((content, item))

    if created and news_channel is not None:
        today = utcnow()
        lines = [f"{n}. {c.title}\n{c.summary}\n原文：{item['url']}" for n, (c, item) in enumerate(created, start=1)]
        lines.append("本文由 AI 根据 GOV.UK 公开信息（Open Government Licence v3.0）整理成中文，发布前经编辑审核；一切以原文为准。")
        digest_post = Content(
            type="post",
            status="pending",
            title=f"今日英国要闻 · {today.month}月{today.day}日",
            summary="；".join(c.title for c, _ in created[:3])[:200],
            body="\n\n".join(lines),
            source_name=SOURCE,
            licence_ref=LICENCE,
            ai_status="ok" if all(c.ai_status == "ok" for c, _ in created) else "check",
        )
        session.add(digest_post)
        session.flush()
        session.add(ChannelItem(channel_id=news_channel.id, content_id=digest_post.id))
    session.commit()
    return {"fetched": len(fresh), "drafted": len(created), "skipped": len(fresh) - len(created), "to_check": to_check}


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
    return (target - local).total_seconds()


def run_once() -> int:
    from app.core.db import get_db

    db = next(get_db())
    try:
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

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Channel, ChannelItem, Content, EventCluster, utcnow


class LLMUnavailable(Exception):
    pass


@dataclass(frozen=True)
class RawItem:
    title: str
    canonical_url: str
    summary: str
    event_key: str
    fulltext: str
    source_name: str = "GOV.UK"
    licence_ref: str = "OGL v3.0"


RULES = (
    (("签证", "visa"), "uk-visa"),
    (("押金", "租房", "tenancy"), "uk-housing"),
)

FIXTURE = (
    RawItem(
        title="签证费将于下月调整",
        canonical_url="https://www.gov.uk/visa-fees",
        summary="内政部更新了签证收费表。",
        event_key="visa-fee",
        fulltext="SECRET FULL TEXT",
    ),
    RawItem(
        title="签证费调整的补充说明",
        canonical_url="https://www.gov.uk/visa-fees-extra",
        summary="学生签证费用同步调整。",
        event_key="visa-fee",
        fulltext="SECRET FULL TEXT",
    ),
    RawItem(
        title="租房押金必须放入保护计划",
        canonical_url="https://www.gov.uk/tenancy-deposit-protection",
        summary="押金需存放在认可计划中。",
        event_key="deposit",
        fulltext="SECRET FULL TEXT",
    ),
)


def call_llm(text: str) -> str:
    key = get_settings().llm_api_key
    if not key or key == "fail":
        raise LLMUnavailable()
    return text[:200]


def route_code(title: str) -> str | None:
    lowered = title.lower()
    for words, code in RULES:
        if any(word.lower() in lowered for word in words):
            return code
    return None


def ingest_fixture(session: Session) -> dict[str, int]:
    return ingest_items(session, FIXTURE)


def ingest_items(session: Session, items: tuple[RawItem, ...] | list[RawItem]) -> dict[str, int]:
    created = 0
    duplicates = 0
    degraded = 0
    for item in items:
        digest = hashlib.sha256(item.canonical_url.strip().lower().encode()).hexdigest()
        if session.scalar(select(Content.id).where(Content.content_hash == digest)) is not None:
            duplicates += 1
            continue
        code = route_code(item.title)
        channel = (
            session.scalar(select(Channel).where(Channel.code == code, Channel.is_active.is_(True)))
            if code
            else None
        )
        if channel is None:
            continue
        summary = (item.summary or "")[:200]
        try:
            summary = call_llm(summary)[:200]
            ai_status = "ok"
        except LLMUnavailable:
            ai_status = "degraded"
            degraded += 1
        cluster = session.scalar(select(EventCluster).where(EventCluster.key == item.event_key))
        if cluster is None:
            cluster = EventCluster(key=item.event_key, title=item.title, source_count=0)
            session.add(cluster)
            session.flush()
        cluster.source_count += 1
        content = Content(
            type="news",
            status="published",
            title=item.title[:200],
            summary=summary,
            body=None,
            canonical_url=item.canonical_url,
            source_name=item.source_name,
            licence_ref=item.licence_ref,
            published_at=utcnow(),
            content_hash=digest,
            ai_status=ai_status,
            event_cluster_id=cluster.id,
        )
        session.add(content)
        session.flush()
        session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
        created += 1
    session.commit()
    return {"created": created, "duplicates": duplicates, "degraded": degraded}

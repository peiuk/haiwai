from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Channel, ChannelItem, Content, utcnow


# 分类信息只能发到 category 匹配的官方频道（POST /listings 会二次校验）。
# 保证「房产 / 市场 / 招聘」三类都有对应频道，旧库也能被幂等补齐。
_CATEGORY_CHANNELS = [
    ("uk-housing", "英国租房", "英國租房", "房产"),
    ("uk-market", "英国二手与市集", "英國二手與市集", "市场"),
    ("uk-jobs", "英国招聘", "英國招聘", "招聘"),
]


# 开通国家时自动建的频道：(代号后缀, 分类, 分类的繁体)，顺序就是前台的排列顺序；频道名 = 国家名 + 分类。
COUNTRY_CHANNELS = [
    ("news", "资讯", "資訊"),
    ("chat", "交流", "交流"),
    ("jobs", "招聘", "招聘"),
    ("housing", "房产", "房產"),
    ("market", "市场", "市場"),
    ("business", "商务", "商務"),
]
# 国际频道各国共享，不加国家名。
GLOBAL_CHANNELS = [
    ("news", "新闻", "新聞"),
    ("film", "影视", "影視"),
    ("health", "健康", "健康"),
    ("tech", "科技", "科技"),
    ("friends", "交友", "交友"),
    ("travel", "旅游", "旅遊"),
]


def ensure_region_channels(session: Session, region_code: str, region_label: str) -> list[Channel]:
    """给一个国家（或国际）补齐默认的官方频道，返回这次新建的。

    幂等：这个国家已有同分类的官方频道就不再建（英国原有的房产 / 市场 / 招聘频道保留原名），只补排序号。
    """
    code = region_code.upper()
    is_global = code == "GLOBAL"
    created: list[Channel] = []
    for order, (slug, category, category_hant) in enumerate(GLOBAL_CHANNELS if is_global else COUNTRY_CHANNELS, start=1):
        channel_code = f"{code.lower()}-{slug}"
        existing = session.scalar(
            select(Channel).where(
                (Channel.code == channel_code)
                | ((Channel.region_code == code) & (Channel.category == category) & Channel.kind.like("official%"))
            )
        )
        if existing is not None:
            if not existing.sort_order:
                existing.sort_order = order
            continue
        prefix = "" if is_global else region_label
        channel = Channel(
            code=channel_code,
            name_hans=f"{prefix}{category}",
            name_hant=f"{prefix}{category_hant}",  # 国家名的繁体可以在后台编辑频道时改
            kind="official_curated",
            region_code=code,
            category=category,
            sort_order=order,
            is_active=True,
        )
        session.add(channel)
        created.append(channel)
    return created


def ensure_channel_categories(session: Session) -> None:
    for code, name_hans, name_hant, category in _CATEGORY_CHANNELS:
        row = session.scalar(select(Channel).where(Channel.code == code))
        if row is None:
            session.add(
                Channel(
                    code=code,
                    name_hans=name_hans,
                    name_hant=name_hant,
                    kind="official_curated",
                    region_code="UK",
                    category=category,
                    is_active=True,
                )
            )
        elif not (row.category or "").strip():
            row.category = category


def seed_if_empty() -> None:
    from app.core.db import get_db

    session = next(get_db())
    try:
        exists = session.scalar(select(Channel.id).where(Channel.code == "uk-housing"))
        if not exists:
            _insert_seed(session)
        ensure_channel_categories(session)
        ensure_region_channels(session, "GLOBAL", "国际")  # 国际频道的分类：新闻、影视、健康、科技、交友、旅游
        _ensure_global_content(session)
        session.commit()
    finally:
        session.close()


def _ensure_global_content(session: Session) -> None:
    """幂等补种：保证「国际华人交流」(GLOBAL) 频道下有种子内容。

    国际频道各国共享，游客（默认 GLOBAL 区域）打开首页依赖它兜底，
    不能空白页（§26.2 洞 1）。老库缺内容时在此补齐。
    """
    global_chat = session.scalar(select(Channel).where(Channel.code == "global-chinese"))
    if global_chat is None:
        return
    has_content = session.scalar(
        select(ChannelItem.content_id)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == global_chat.id,
            Content.status == "published",
            Content.deleted_at.is_(None),
        )
        .limit(1)
    )
    if has_content is not None:
        return
    now = utcnow()
    community = Content(
        type="post",
        status="published",
        title="欢迎来到海外圈",
        title_hant="歡迎來到海外圈",
        summary="这里是面向全球华人的中文社区，分享本地生活、租房、签证与求职经验。",
        summary_hant="這裡是面向全球華人的中文社區，分享本地生活、租房、簽證與求職經驗。",
        source_name="海外圈",
        licence_ref="",
        canonical_url=None,
        published_at=now - timedelta(hours=3),
    )
    etiquette = Content(
        type="post",
        status="published",
        title="社区规范与内容守则",
        title_hant="社區規範與內容守則",
        summary="友善交流，尊重当地法律；转载请注明来源并附许可。",
        summary_hant="友善交流，尊重當地法律；轉載請註明來源並附許可。",
        source_name="海外圈",
        licence_ref="",
        canonical_url=None,
        published_at=now - timedelta(hours=2),
    )
    session.add_all([community, etiquette])
    session.flush()
    session.add_all(
        [
            ChannelItem(channel_id=global_chat.id, content_id=community.id, pinned=True, added_at=now - timedelta(hours=3)),
            ChannelItem(channel_id=global_chat.id, content_id=etiquette.id, added_at=now - timedelta(hours=2)),
        ]
    )


def _insert_seed(session: Session) -> None:
    now = utcnow()
    housing = Channel(
        code="uk-housing",
        name_hans="英国租房",
        name_hant="英國租房",
        kind="official_curated",
        region_code="UK",
        is_active=True,
    )
    visa = Channel(
        code="uk-visa",
        name_hans="签证与政策",
        name_hant="簽證與政策",
        kind="official_auto",
        region_code="UK",
        is_active=True,
    )
    global_chat = Channel(
        code="global-chinese",
        name_hans="国际华人交流",
        name_hant="國際華人交流",
        kind="official_curated",
        region_code="GLOBAL",
        is_active=True,
    )
    deposit = Content(
        type="post",
        status="published",
        title="押金保护说明",
        title_hant="押金保護說明",
        summary="押金须放入政府认可的押金保护计划。",
        summary_hant="押金須放入政府認可的押金保護計劃。",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/tenancy-deposit-protection",
        published_at=now - timedelta(hours=5),
    )
    fee = Content(
        type="news",
        status="published",
        title="签证费调整",
        summary="内政部公布新的签证收费。",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/visa-fees",
        published_at=now - timedelta(hours=1),
    )
    checklist = Content(
        type="news",
        status="published",
        title="租房合同检查清单",
        summary="签约前核对押金、账单和最短租期。",
        source_name="GOV.UK",
        licence_ref="OGL v3.0",
        canonical_url="https://www.gov.uk/private-renting",
        published_at=now - timedelta(minutes=30),
    )
    session.add_all([housing, visa, global_chat, deposit, fee, checklist])
    session.flush()
    session.add_all(
        [
            ChannelItem(channel_id=housing.id, content_id=deposit.id, pinned=True, added_at=now - timedelta(hours=5)),
            ChannelItem(channel_id=visa.id, content_id=fee.id, added_at=now - timedelta(hours=1)),
            ChannelItem(channel_id=housing.id, content_id=checklist.id, added_at=now - timedelta(hours=2)),
            ChannelItem(channel_id=visa.id, content_id=checklist.id, added_at=now - timedelta(minutes=20)),
        ]
    )

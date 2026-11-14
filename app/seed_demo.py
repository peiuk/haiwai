"""演示数据种子：生成真实示例图片 + 示例用户发帖（图文/话题/多图），供首页/频道/房间查看效果。

用法（在项目根目录，激活 venv）：
    python -m app.seed_demo

幂等：已存在 demo 内容时跳过（可用 --force 重灌）。
图片用标准库 zlib+struct 生成真实 PNG，写入 data/uploads/，并登记 upload_object。
"""
from __future__ import annotations

import json
import math
import os
import struct
import zlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    Channel,
    ChannelItem,
    ChannelSubscription,
    Content,
    ContentReaction,
    RoomComment,
    UploadObject,
    User,
    UserRegionPref,
    new_id,
    utcnow,
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")


# --------------------------------------------------------------------------- #
# 图片生成（纯标准库，真实 PNG）
# --------------------------------------------------------------------------- #
def _chunk(typ: bytes, data: bytes) -> bytes:
    c = struct.pack(">I", len(data)) + typ + data
    c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return c


def make_png(path: str, w: int, h: int, rgb) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: None
        for x in range(w):
            r, g, b = rgb(x, y, w, h)
            raw += bytes((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))


def _lerp(a, b, t):
    return a + (b - a) * t


def scene_skyline(x, y, w, h):
    """黄昏天际线 + 建筑剪影 + 圆月，模拟城市夜景。"""
    t = y / h
    r = int(_lerp(255, 40, t))
    g = int(_lerp(150, 30, t))
    b = int(_lerp(90, 60, t))
    # 圆月
    mx, my, mr = w * 0.72, h * 0.28, h * 0.12
    if (x - mx) ** 2 + (y - my) ** 2 < mr * mr:
        return 250, 245, 220
    # 建筑剪影（几栋矩形，高度随 x 正弦变化）
    bh = int(h * 0.35 + h * 0.2 * (0.5 + 0.5 * math.sin(x / 90.0)))
    if y > h - bh:
        return 25, 22, 40
    # 窗户亮点
    if y > h - bh + 20 and (x // 28) % 3 == 0 and (y // 40) % 3 == 1:
        return 255, 210, 120
    return r, g, b


def scene_food(x, y, w, h):
    """暖色餐盘 + 圆盘 + 食材点，模拟美食。"""
    r = int(_lerp(245, 210, y / h))
    g = int(_lerp(235, 170, y / h))
    b = int(_lerp(220, 140, y / h))
    cx, cy, cr = w * 0.5, h * 0.52, h * 0.34
    d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    if d < cr:
        # 餐盘外圈
        if d > cr * 0.85:
            return 120, 80, 60
        # 食材色块
        ang = math.atan2(y - cy, x - cx)
        seg = int((ang / (2 * math.pi) + 1) * 6) % 6
        colors = [(200, 60, 50), (90, 160, 70), (230, 180, 60), (60, 140, 150), (180, 100, 120), (240, 220, 150)]
        return colors[seg]
    return r, g, b


def scene_home(x, y, w, h):
    """室内暖光：墙面渐变 + 窗户 + 绿植。"""
    r = int(_lerp(235, 200, y / h))
    g = int(_lerp(228, 180, y / h))
    b = int(_lerp(215, 150, y / h))
    # 窗户
    wx0, wy0, ww, wh = w * 0.15, h * 0.18, w * 0.3, h * 0.42
    if wx0 <= x <= wx0 + ww and wy0 <= y <= wy0 + wh:
        return 175, 210, 235
    # 窗框
    if (abs(x - wx0) < 4 or abs(x - wx0 - ww) < 4 or abs(y - wy0) < 4 or abs(y - wy0 - wh) < 4) and wx0 - 4 <= x <= wx0 + ww + 4 and wy0 - 4 <= y <= wy0 + wh + 4:
        return 90, 70, 50
    # 绿植
    if x > w * 0.72 and y > h * 0.35:
        if (x - w * 0.85) ** 2 + (y - h * 0.75) ** 2 < (h * 0.28) ** 2:
            return 60, 130, 70
    return r, g, b


def scene_market(x, y, w, h):
    """二手市集：桌面 + 散落物品色块。"""
    r = int(_lerp(220, 190, y / h))
    g = int(_lerp(220, 180, y / h))
    b = int(_lerp(215, 170, y / h))
    if y > h * 0.62:
        return 150, 110, 70  # 桌面
    # 物品方块
    for (ix, iy, iw, ih, col) in [
        (0.15, 0.35, 0.18, 0.16, (200, 60, 50)),
        (0.40, 0.30, 0.16, 0.20, (70, 140, 200)),
        (0.62, 0.38, 0.20, 0.14, (90, 170, 90)),
        (0.28, 0.52, 0.14, 0.10, (230, 180, 60)),
    ]:
        if w * ix <= x <= w * (ix + iw) and h * iy <= y <= h * (iy + ih):
            return col
    return r, g, b


SCENES = {
    "skyline": scene_skyline,
    "food": scene_food,
    "home": scene_home,
    "market": scene_market,
}


def make_image(session: Session, owner_id: str, scene: str, w: int = 900, h: int = 560) -> str:
    key = new_id().replace("-", "")
    path = os.path.join(UPLOAD_DIR, key)
    make_png(path, w, h, SCENES[scene])
    session.add(UploadObject(key=key, owner_id=owner_id, content_type="image/png", stored=True))
    return key


# --------------------------------------------------------------------------- #
# 种子数据
# --------------------------------------------------------------------------- #
def run(force: bool = False) -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    session = next(get_db())
    try:
        # 幂等：已有 demo 帖子则跳过（除非 force）
        marker = session.scalar(select(Content.id).where(Content.title == "【演示】伦敦二区阳光一居转租"))
        if marker and not force:
            print("演示数据已存在，跳过（--force 可重灌）。")
            return

        now = utcnow()

        # 取现有用户作为作者（优先有 phone_verified 的）
        users = session.scalars(select(User).where(User.status == "active")).all()
        by_handle = {u.handle: u for u in users if u.handle}
        by_name = {u.display_name: u for u in users}
        pei = by_name.get("裴总") or users[0]
        # 找/建几个有"人味"的作者：直接用现有用户，缺则复用 pei
        author_li = by_name.get("联调用户") or pei
        author_rui = by_name.get("Rui") or pei
        author_ui = by_name.get("UI设计验证") or pei
        author_test = by_name.get("测试用户") or pei

        # 取频道
        channels = {c.code: c for c in session.scalars(select(Channel)).all()}
        housing = channels.get("uk-housing")
        market = channels.get("uk-market")
        jobs = channels.get("uk-jobs")
        gchat = channels.get("global-chinese")
        room = channels.get("room-4960fb29")  # 伦敦看房笔记
        visa = channels.get("uk-visa")

        def add_post(
            author: User,
            channel: Channel | None,
            title: str,
            body: str,
            scenes: list[str],
            keywords: list[str],
            hours_ago: float,
            ctype: str = "post",
            reactions: int = 0,
        ) -> Content:
            keys = [make_image(session, author.id, s) for s in scenes]
            content = Content(
                type=ctype,
                status="published",
                author_id=author.id,
                title=title,
                summary=body[:500],
                body=body,
                keywords_json=json.dumps(keywords, ensure_ascii=False),
                keyword_source="user",
                source_name=author.display_name,
                image_key=keys[0] if keys else None,
                image_keys_json=json.dumps(keys),
                published_at=now - timedelta(hours=hours_ago),
                created_at=now - timedelta(hours=hours_ago),
            )
            session.add(content)
            session.flush()
            if channel is not None:
                session.add(ChannelItem(channel_id=channel.id, content_id=content.id, added_at=now - timedelta(hours=hours_ago)))
            if reactions:
                for u in users[:reactions]:
                    session.add(ContentReaction(user_id=u.id, content_id=content.id, liked=True))
            return content

        # ---- 1. 多图帖子（4 张，房产）----
        p1 = add_post(
            author_li, housing,
            "【演示】伦敦二区阳光一居转租",
            "Zone 2 步行 8 分钟到地铁站，一室一厅带独立厨房，月租 1450 镑不包 bills。押金已入 TDS 保护计划，随时可约看房。",
            ["home", "skyline", "home", "market"], ["伦敦租房", "Zone2", "转租"], 1.2, reactions=3,
        )
        # ---- 2. 双图帖子（美食）----
        add_post(
            author_rui, gchat,
            "【演示】周末在家做了顿中餐",
            "红烧肉 + 手撕包菜，海外也能吃到家的味道。分享做法，评论区交流～",
            ["food", "food"], ["美食", "伦敦生活"], 3.5, reactions=5,
        )
        # ---- 3. 单图话题 ----
        add_post(
            author_ui, gchat,
            "【演示】伦敦今天的天际线",
            "下班路过泰晤士河，随手拍了一张，晚霞真的绝了。#伦敦 #晚霞",
            ["skyline"], ["伦敦", "晚霞", "拍照"], 5.0, ctype="topic", reactions=4,
        )
        # ---- 4. 二手市集 3 图 ----
        add_post(
            author_test, market,
            "【演示】搬家出二手家具",
            "宜家书桌、台灯、单人床垫，九成新，价格可议。自取或约时间送货。",
            ["market", "home", "market"], ["二手", "搬家", "伦敦"], 8.0, reactions=2,
        )
        # ---- 5. 纯文字招聘 ----
        add_post(
            author_li, jobs,
            "【演示】招中餐后厨兼职",
            "伦敦唐人街中餐馆招兼职后厨，会基础刀工即可，包餐，时薪 12 镑。欢迎私信。",
            [], ["招聘", "中餐", "兼职"], 12.0, reactions=1,
        )
        # ---- 6. 房间投稿（伦敦看房笔记）多图 ----
        add_post(
            author_rui, room,
            "【演示】上周去看的三套房子对比",
            "Canary Wharf、Camden、Brixton 三个片区都跑了一遍，各有优劣，整理成笔记供参考。",
            ["home", "skyline", "home"], ["看房", "伦敦", "租房"], 18.0, reactions=3,
        )
        # ---- 7. 签证政策讨论（话题）----
        add_post(
            author_ui, visa,
            "【演示】学生签证转工签时间线分享",
            "从 PSW 到 Skilled Worker，全程 6 周，中间补了一次材料。有问题的评论区见。",
            [], ["签证", "工签", "PSW"], 26.0, ctype="topic", reactions=2,
        )

        # ---- 给帖子加评论，让回复弹窗有内容 ----
        def add_comment(content: Content, author: User, body: str, hours_ago: float) -> None:
            session.add(
                RoomComment(
                    room_id=(gchat.id if gchat else content.author_id),
                    content_id=content.id,
                    author_id=author.id,
                    body=body,
                    status="approved",
                    created_at=now - timedelta(hours=hours_ago),
                )
            )

        add_comment(p1, author_rui, "房子还在吗？什么时候方便看房？", 1.0)
        add_comment(p1, author_test, "位置很好，已私信你。", 0.8)
        add_comment(p1, author_ui, "请问可以养宠物吗？", 0.5)

        # ---- 让"裴总"（主登录账号）能看全：补 UK 区域 + 订阅 UK 频道 ----
        if pei and session.get(UserRegionPref, pei.id) is None:
            session.add(UserRegionPref(user_id=pei.id, region_code="UK", source="manual", locked=False))
        if pei:
            for ch in [housing, market, jobs, visa, gchat]:
                if ch is not None and session.get(ChannelSubscription, (pei.id, ch.id)) is None:
                    session.add(ChannelSubscription(user_id=pei.id, channel_id=ch.id))

        # ---- 补充 global-chinese 内容：让游客 / GLOBAL 用户也能看到多图效果 ----
        _g_exist = session.scalar(
            select(Content.id).where(Content.title == "【演示】伦敦周末集市随手拍")
        )
        if not _g_exist and gchat is not None:
            add_post(
                author_test, gchat,
                "【演示】伦敦周末集市随手拍",
                "周六去了 Borough Market，人超多。拍了点摊位和街头艺人，分享给大家。",
                ["market", "food", "skyline"], ["伦敦", "市集", "周末"], 2.0, reactions=3,
            )
            add_post(
                author_ui, gchat,
                "【演示】新租的房子布置好啦",
                "搬进来两周，终于把客厅收拾出来。阳光房太治愈了，随手记录一下。",
                ["home", "home"], ["伦敦", "家居", "租房"], 6.5, reactions=2,
            )

        session.commit()
        print("演示数据已写入：")
        print(f"  图片：{len(session.scalars(select(UploadObject)).all())} 个 upload_object")
        print("  帖子：含多图（2-4 张）/ 单图 / 纯文字 / 话题")
        print("  评论：3 条")
        print("  已为「裴总」补 UK 区域 + 订阅 UK 频道")
        print("  已补 global-chinese 频道多图内容（游客/GLOBAL 用户可见）")
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    run(force="--force" in sys.argv)

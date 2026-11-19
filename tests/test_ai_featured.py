"""AI 精选：只从最近公开的用户内容里选、最多 5 条、7 天后自动取消；人工设的不过期；人工取消过的不再选。"""
from datetime import timedelta

from sqlalchemy import select

import app.ai_featured as ai
from app.models import AuditLog, Channel, ChannelItem, Content, User, utcnow
from tests.test_news import make_admin
from tests.test_rooms import headers, register


def setup(client):
    register(client, "poster@example.com")
    session = client.session_factory()
    author = session.scalar(select(User).where(User.email == "poster@example.com"))
    public = Channel(code="uk-chat", name_hans="英国交流", name_hant="英國交流", kind="official_curated", region_code="UK", is_active=True)
    private = Channel(code="room-secret", name_hans="私密房", name_hant="私密房", kind="room", region_code="UK", is_active=True, is_private=True)
    session.add_all([public, private])
    session.flush()

    def post(title, channel=public, **extra):
        content = Content(type=extra.pop("type", "post"), status=extra.pop("status", "published"), author_id=author.id, title=title, body=f"{title} 的正文", **extra)
        session.add(content)
        session.flush()
        session.add(ChannelItem(channel_id=channel.id, content_id=content.id))
        return content.id

    ids = {f"ok{i}": post(f"好帖{i}") for i in range(7)}
    ids["private"] = post("私密房间的帖", channel=private)
    ids["pending"] = post("待审的帖", status="pending")
    ids["repost"] = post("转发", type="repost")
    ids["old"] = post("三天前的帖", created_at=utcnow() - timedelta(days=3))
    session.commit()
    session.close()
    return ids


def test_picks_only_recent_public_posts_and_caps_at_five(client):
    setup(client)
    seen: list[str] = []

    def fake_ask(listing):
        seen.append(listing)
        # 越界、重复的编号要丢掉；给 8 条也只取 5 条
        return [ai.Pick(index=i, reason=f"理由{i}") for i in [0, 0, 99, 1, 2, 3, 4, 5, 6]]

    session = client.session_factory()
    result = ai.run_ai_featured(session, ask=fake_ask)
    assert result == {"expired": 0, "candidates": 7, "picked": 5}
    for word in ("私密房间", "待审", "转发", "三天前"):
        assert word not in seen[0]
    picked = session.scalars(select(Content).where(Content.featured_at.is_not(None))).all()
    assert len(picked) == 5
    assert all(c.ai_featured_until is not None and c.ai_featured_until - c.featured_at == ai.KEEP for c in picked)
    assert session.scalar(select(AuditLog.detail).where(AuditLog.action == ai.PICK_ACTION, AuditLog.target_id == picked[0].id)).startswith("理由")
    session.close()


def test_ai_picks_expire_manual_ones_stay_and_cancelled_are_not_repicked(client):
    ids = setup(client)
    session = client.session_factory()
    ai.run_ai_featured(session, ask=lambda listing: [ai.Pick(index=0, reason="好"), ai.Pick(index=1, reason="好")])
    first, second = session.scalars(select(Content).where(Content.ai_featured_until.is_not(None))).all()
    first_id, second_id, first_title = first.id, second.id, first.title
    session.close()

    # 管理员取消一条 AI 精选、再手动精选另一条好帖：手动的不带到期时间
    token = make_admin(client, "feature-admin@example.com")
    assert client.post(f"/api/v1/admin/contents/{first_id}/featured", headers=headers(token), json={"featured": False}).status_code == 200
    manual_id = next(cid for key, cid in ids.items() if key.startswith("ok") and cid not in (first_id, second_id))
    assert client.post(f"/api/v1/admin/contents/{manual_id}/featured", headers=headers(token), json={"featured": True}).status_code == 200
    listed = {row["content_id"]: row for row in client.get("/api/v1/admin/contents?type=post", headers=headers(token)).json()["items"]}
    assert listed[second_id]["ai_featured_until"] and listed[manual_id]["ai_featured_until"] is None

    # 过了 7 天：AI 那条自动取消，手动那条还在；取消过的那条不再进候选
    session = client.session_factory()
    session.get(Content, second_id).ai_featured_until = utcnow() - timedelta(minutes=1)
    session.commit()
    seen: list[str] = []
    result = ai.run_ai_featured(session, ask=lambda listing: seen.append(listing) or [])
    assert result["expired"] == 1
    assert session.get(Content, second_id).featured_at is None
    assert session.get(Content, manual_id).featured_at is not None
    assert f"标题：{first_title}\n" not in seen[0]
    session.close()


def test_no_key_means_nothing_changes(client, monkeypatch):
    setup(client)
    import app.llm as llm

    monkeypatch.setattr(llm, "get_settings", lambda: type("S", (), {"llm_api_key": "", "llm_api_base": "", "llm_model": ""})())
    session = client.session_factory()
    try:
        ai.run_ai_featured(session)
        raise AssertionError("没配密钥应该报 LLMUnavailable")
    except llm.LLMUnavailable:
        pass
    assert session.scalar(select(Content.id).where(Content.featured_at.is_not(None))) is None
    session.close()

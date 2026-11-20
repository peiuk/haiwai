"""后台「抓取今日资讯」在后台跑：POST 立刻返回 202，GET 查进度和结果；失败要记下原因；正在跑时不能再开一次。"""
from datetime import timedelta

import app.api.v1.ingest as ingest
from app.models import AuditLog
from tests.test_news import make_admin
from tests.test_rooms import headers

URL = "/api/v1/admin/ingest/news"


def test_runs_in_background_and_reports_result(client, monkeypatch):
    auth = headers(make_admin(client, "ingest-ok@example.com"))
    assert client.get(URL, headers=auth).json() == {"running": False, "ok": None, "detail": None}
    result = {"fetched": 3, "drafted": 2, "skipped": 1, "to_check": 1, "digest": 0}
    monkeypatch.setattr(ingest, "run_daily_news", lambda session: result)

    started = client.post(URL, headers=auth)  # TestClient 等后台任务跑完才返回
    assert started.status_code == 202 and started.json()["running"] is True
    status = client.get(URL, headers=auth).json()
    assert status["running"] is False and status["ok"] is True
    assert "新抓到 3 条，生成 2 条中文稿" in status["detail"] and "1 条数字需要对照原文" in status["detail"]


def test_failure_is_recorded_with_reason(client, monkeypatch):
    auth = headers(make_admin(client, "ingest-down@example.com"))

    def down(session):
        raise ingest.NewsUnavailable("AI 调用失败：The read operation timed out")

    monkeypatch.setattr(ingest, "run_daily_news", down)
    assert client.post(URL, headers=auth).status_code == 202
    status = client.get(URL, headers=auth).json()
    assert status == {"running": False, "ok": False, "detail": "AI 调用失败：The read operation timed out"}


def test_busy_while_running_and_stale_run_can_be_restarted(client, monkeypatch):
    auth = headers(make_admin(client, "ingest-busy@example.com"))
    session = client.session_factory()
    session.add(AuditLog(action=ingest.STARTED))  # 另一个 worker 正在抓
    session.commit()
    assert client.get(URL, headers=auth).json()["running"] is True
    busy = client.post(URL, headers=auth)
    assert busy.status_code == 409 and busy.json()["code"] == "NEWS_BUSY"

    # 进程中途被重启、一直没结果的那次，过了 15 分钟就不再挡着
    run = session.query(AuditLog).filter_by(action=ingest.STARTED).one()
    run.created_at = run.created_at - ingest.STALE_AFTER - timedelta(minutes=1)
    session.commit()
    session.close()
    monkeypatch.setattr(ingest, "run_daily_news", lambda session: {"fetched": 0, "drafted": 0, "skipped": 0, "to_check": 0, "digest": 0})
    assert client.post(URL, headers=auth).status_code == 202
    assert client.get(URL, headers=auth).json()["detail"] == "GOV.UK 和 BBC 暂时没有新资讯。"

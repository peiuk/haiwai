"""后台「抓取今日资讯」：AI 写稿要两三分钟，按钮只负责在后台开跑，页面每隔几秒来问一次进度。

进度记在操作日志里（开始 / 完成 / 失败各一条），线上开了多个 worker 也能查到同一份。
"""
from datetime import timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import APIError
from app.api.v1.admin import require_admin
from app.core.audit import note_server_error, write_audit
from app.models import AuditLog, User, utcnow
from app.news import NewsUnavailable, run_daily_news

router = APIRouter(prefix="/admin/ingest", tags=["ingest"])

STARTED, DONE, FAILED = "admin.news.start", "admin.news.fetch", "admin.news.failed"
# 开始了这么久还没有结果，当作进程中途被重启、这次没跑完，允许重新抓
STALE_AFTER = timedelta(minutes=15)


def news_status(session: Session) -> dict:
    last = session.scalar(
        select(AuditLog).where(AuditLog.action.in_((STARTED, DONE, FAILED))).order_by(AuditLog.created_at.desc()).limit(1)
    )
    if last is None:
        return {"running": False, "ok": None, "detail": None}
    if last.action == STARTED:
        started = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=timezone.utc)  # SQLite 读出来不带时区
        return {"running": started > utcnow() - STALE_AFTER, "ok": None, "detail": None}
    return {"running": False, "ok": last.action == DONE, "detail": last.detail}


def describe(result: dict[str, int]) -> str:
    digest = "已把之前通过的资讯汇成「今日英国要闻」发布。" if result["digest"] else ""
    if not result["fetched"]:
        return f"GOV.UK 和 BBC 暂时没有新资讯。{digest}"
    check = f"，其中 {result['to_check']} 条数字需要对照原文" if result["to_check"] else ""
    return f"新抓到 {result['fetched']} 条，生成 {result['drafted']} 条中文稿（{result['skipped']} 条和华人生活关系不大，已跳过）{check}。{digest}"


def fetch_in_background(bind: Engine | Connection, admin_id: str) -> None:
    # 请求用的数据库会话在响应发出后就关了，这里另开一个连同一个库的
    with Session(bind=bind, expire_on_commit=False) as session:
        try:
            action, detail = DONE, describe(run_daily_news(session))
        except NewsUnavailable as err:
            session.rollback()
            action, detail = FAILED, str(err)
        except IntegrityError:  # 定时任务正好也在跑，同一篇新闻被它先存了
            session.rollback()
            action, detail = FAILED, "定时任务也在抓取，同一篇新闻被它先存了，稍后刷新页面查看"
        except Exception as err:  # 不记下失败，页面会一直显示「正在抓取」直到超时
            session.rollback()
            note_server_error()
            action, detail = FAILED, f"抓取出错：{err!r}"
        write_audit(session, admin_id, action, "content", None, detail[:300])
        session.commit()


@router.post("/news", status_code=202)
def fetch_news(
    background: BackgroundTasks, admin: User = Depends(require_admin), session: Session = Depends(get_db)
) -> dict:
    """抓取 GOV.UK 和 BBC 最新资讯并让 AI 写成中文稿，全部进「待审核」，由管理员发布。在后台跑，用 GET 查进度。"""
    if news_status(session)["running"]:
        raise APIError(409, "NEWS_BUSY", "已有一次抓取正在进行，完成后会显示结果")
    write_audit(session, admin.id, STARTED, "content")
    session.commit()
    background.add_task(fetch_in_background, session.get_bind(), admin.id)
    return {"running": True, "ok": None, "detail": None}


@router.get("/news")
def fetch_news_status(admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict:
    """running：还在抓；跑完后 ok 表示成没成功，detail 是结果或失败原因。"""
    return news_status(session)

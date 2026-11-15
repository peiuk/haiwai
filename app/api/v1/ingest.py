from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.api.v1.admin import require_admin
from app.core.audit import write_audit
from app.ingest import ingest_fixture
from app.models import User
from app.news import NewsUnavailable, run_daily_news

router = APIRouter(prefix="/admin/ingest", tags=["ingest"])


@router.post("/fixture")
def fetch_fixture(
    _: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    if get_settings().app_env != "dev":
        raise APIError(404, "NOT_FOUND", "不存在")
    return ingest_fixture(session)


@router.post("/news")
def fetch_news(admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict[str, int]:
    """抓取 GOV.UK 最新资讯并让 AI 写成中文稿，全部进「待审核」，由管理员发布。"""
    try:
        result = run_daily_news(session)
    except NewsUnavailable as err:
        raise APIError(503, "NEWS_UNAVAILABLE", str(err)) from err
    except IntegrityError as err:  # 定时任务正好也在跑，同一篇新闻被它先存了
        session.rollback()
        raise APIError(409, "NEWS_BUSY", "已有一次抓取正在进行，请稍后刷新页面查看") from err
    write_audit(session, admin.id, "admin.news.fetch", "content", None, f"生成 {result['drafted']} 条")
    session.commit()
    return result

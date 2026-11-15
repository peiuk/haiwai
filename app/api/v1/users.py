from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import optional_user
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.models import Content, ModerationCase, User, UserBlock, UserFollow
from app.privacy import can_view_content
from app.reports import ReportBody, report_receipt

router = APIRouter()


def _profile(session: Session, user_id: str) -> User:
    profile = session.get(User, user_id)
    if profile is None or profile.deleted_at is not None or profile.status != "active":
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    return profile


@router.get("/users/{user_id}")
def public_profile(
    user_id: str,
    viewer: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    profile = _profile(session, user_id)
    following = False
    blocked = False
    if viewer is not None:
        following = session.get(UserFollow, (viewer.id, profile.id)) is not None
        blocked = session.get(UserBlock, (viewer.id, profile.id)) is not None
    return {
        "user_id": profile.id,
        "display_name": profile.display_name,
        "handle": profile.handle or "",
        "avatar_tone": profile.avatar_tone,
        "city_label": profile.city_label or "",
        "following": following,
        "blocked": blocked,
    }


@router.post("/users/{user_id}/report")
def report_user(
    user_id: str,
    body: ReportBody,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    profile = _profile(session, user_id)
    if user is not None and profile.id == user.id:
        raise APIError(403, "SELF_REPORT", "不能举报自己")
    if user is not None:
        existing = session.scalar(
            select(ModerationCase.id).where(
                ModerationCase.reported_user_id == profile.id,
                ModerationCase.reporter_id == user.id,
            )
        )
        if existing:
            raise APIError(409, "DUPLICATE_REPORT", "你已经举报过这个用户")
    case = ModerationCase(
        reported_user_id=profile.id,
        reporter_id=user.id if user else None,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(case)
    session.flush()
    write_audit(session, user.id if user else None, "user.report", "user", profile.id)
    session.commit()
    return report_receipt(case)


@router.get("/users/{user_id}/posts")
def public_posts(user_id: str, session: Session = Depends(get_db)) -> dict[str, list[dict[str, str | None]]]:
    profile = _profile(session, user_id)
    rows = session.scalars(
        select(Content)
        .where(Content.author_id == profile.id, Content.deleted_at.is_(None), Content.status == "published")
        .order_by(Content.created_at.desc())
        .limit(50)  # shortcut: 主页只显示最近 50 条；要看更早的再加游标分页
    ).all()
    rows = [row for row in rows if can_view_content(session, row, None)]
    return {
        "items": [
            {
                "content_id": row.id,
                "title": row.title,
                "type": row.type,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }

"""自动拦截：不用等人工发现，先把可疑内容挡进待审核。

发帖本身的频率限制在各发布接口里（每小时 5 条帖子、每分钟 5 条留言），新用户前几条帖子本来就要审；
这里补两条：敏感词 / 链接黑名单，和多人举报自动先隐藏。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.models import BlockedTerm, Content, ModerationCase

AUTO_HIDE_REPORTS = 3  # 同一条内容有这么多条未处理的举报，就先隐藏等管理员看


def blocked_term_in(session: Session, *texts: str | None) -> str | None:
    """文字里出现了黑名单上的词或链接时返回命中的那一条，否则 None。不分大小写。"""
    # shortcut: 每次发帖把整张黑名单读出来逐条比对；词条上千以后换成缓存或 Aho-Corasick。
    haystack = " ".join(text for text in texts if text).lower()
    for term in session.scalars(select(BlockedTerm.term)):
        if term in haystack:
            return term
    return None


def hide_if_widely_reported(session: Session, content: Content) -> bool:
    """举报攒够数就把内容放回待审核（对外不再显示），管理员看过后通过或拒绝。返回是否隐藏了。"""
    if content.status != "published":
        return False
    open_cases = session.scalar(
        select(func.count()).select_from(ModerationCase).where(ModerationCase.content_id == content.id, ModerationCase.status == "open")
    )
    if (open_cases or 0) < AUTO_HIDE_REPORTS:
        return False
    content.status = "pending"
    write_audit(session, None, "auto.hide", "content", content.id, f"{open_cases} 条未处理的举报，自动隐藏待审")
    return True

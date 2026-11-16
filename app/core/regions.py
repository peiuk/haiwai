"""已开通国家（单一数据源）。

内置英国和国际；其余国家由后台开通，存在 region 表里。
后端校验（me.py）、内容可见性回落（recommend.py）、后台国家管理都从这里派生。
"""
from contextvars import ContextVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Region

# 游客在首页国家栏选的国家（前端放在 X-Region 请求头里，main.py 的中间件写进来）。
# 只在没登录时用：登录用户以账号里的国家设置为准。
guest_region: ContextVar[str] = ContextVar("guest_region", default="")

# 代码 -> (中文名, 分站城市)。库里没有记录时的默认值；库里有同代码记录时以库为准。
DEFAULT_REGIONS: dict[str, tuple[str, str]] = {
    "UK": ("英国", "伦敦"),
    "GLOBAL": ("国际", ""),
}


def open_regions(session: Session) -> dict[str, tuple[str, str]]:
    """已开通的国家，国际（GLOBAL）恒在且排最后。"""
    result = dict(DEFAULT_REGIONS)
    for row in session.scalars(select(Region).order_by(Region.created_at, Region.code)):
        if row.is_open:
            result[row.code] = (row.name_hans, row.city)
        elif row.code != "GLOBAL":  # 国际频道各国共享，不能关
            result.pop(row.code, None)
    result["GLOBAL"] = result.pop("GLOBAL")
    return result


def is_open_region(session: Session, code: str | None) -> bool:
    return bool(code) and code.upper() in open_regions(session)


def region_name(session: Session, code: str | None) -> str:
    if not code:
        return ""
    return open_regions(session).get(code.upper(), (code, ""))[0]

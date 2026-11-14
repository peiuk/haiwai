"""已开通国家（单一数据源）。

代码 -> (中文名, 分站城市)。新增国家时只需在此追加，
后端校验（me.py）与内容可见性回落（recommend.py）都从这里派生。
"""

OPEN_REGIONS: dict[str, tuple[str, str]] = {
    "UK": ("英国", "伦敦"),
    "GLOBAL": ("国际", ""),
}


def open_region_codes() -> list[str]:
    return list(OPEN_REGIONS.keys())


def is_open_region(code: str | None) -> bool:
    """国家是否已开通（GLOBAL 恒视为已开通）。"""
    if not code:
        return False
    return code.upper() in OPEN_REGIONS


def region_name(code: str | None) -> str:
    if not code:
        return ""
    return OPEN_REGIONS.get(code.upper(), (code, ""))[0]

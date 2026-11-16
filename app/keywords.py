import json
import re

AI_MAX = 5
_LEXICON = (
    ("租房", re.compile(r"租房|房租|租金|整租|出租|求租|租屋")),
    ("合租", re.compile(r"合租|室友|单间")),
    ("二手", re.compile(r"二手|转让|闲置")),
    ("招聘", re.compile(r"招聘|岗位|面试|简历")),
    ("签证", re.compile(r"签证|visa|BRP", re.I)),
)
_CATEGORIES = {"房产", "招聘", "市场", "生活", "交流", "活动"}


_TOKEN = re.compile(r"^[\w\u4e00-\u9fff_]{1,12}$")
_HASH = re.compile(r"[#\uff03]([\w\u4e00-\u9fff_]{1,12})")  # \u4e2d\u6587\u8f93\u5165\u6cd5\u5e38\u6253\u51fa\u5168\u89d2 \uff03


def keyword_source_for(source: str | None, keywords: list[str]) -> str | None:
    if not keywords:
        return None
    if source is None:
        return "user"
    if source not in {"ai_auto", "user"}:
        raise ValueError("关键词来源不正确")
    return source


def clean_city_topic(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    token = value.strip().lstrip("#")
    if not _TOKEN.fullmatch(token):
        raise ValueError("城市话题需要 1 到 12 个字，不能有空格")
    return token


def collect_keywords(explicit: list[str], body: str) -> list[str]:
    found: list[str] = []
    for word in explicit:
        token = word.strip().lstrip("#")
        if _TOKEN.fullmatch(token) and token not in found:
            found.append(token)
        if len(found) >= AI_MAX:
            return found
    for token in _HASH.findall(body):
        if token not in found:
            found.append(token)
        if len(found) >= AI_MAX:
            break
    return found


def dump_keywords(words: list[str]) -> str:
    return json.dumps(words, ensure_ascii=False)


def load_keywords(raw: str | None) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def resolve_keywords(
    explicit: list[str],
    title: str,
    body: str,
    source: str | None,
    category: str | None = None,
) -> tuple[list[str], str | None]:
    words = collect_keywords(explicit, body)
    if words:
        return words, keyword_source_for(source, words)
    suggested = suggest_keywords(title, body, category)
    if not suggested:
        return [], None
    return suggested, "ai_auto"


def suggest_keywords(title: str, body: str, category: str | None = None) -> list[str]:
    text = f"{title}\n{body}"
    if len(text.replace(" ", "")) < 6:
        return []
    out: list[str] = []
    if category in _CATEGORIES:
        out.append(category)
    for word, pattern in _LEXICON:
        if pattern.search(text) and word not in out and len(word) <= 12:
            out.append(word)
        if len(out) >= AI_MAX:
            break
    return out[:AI_MAX]

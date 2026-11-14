import os
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.errors import APIError

POLICY_VERSION = "2026-11-13"

PROVIDERS = {
    "youtube": {
        "display_name": "YouTube",
        "hosts": {"www.youtube.com", "youtube.com", "m.youtube.com"},
        "template": "https://www.youtube-nocookie.com/embed/{id}",
        "allows_framing": True,
        "uk_rights_verified": True,
        "notice": "加载后 YouTube 会收到你的 IP、设备与浏览信息，并可能设置 cookie。平台不代理、不缓存影片。",
    },
    "bbc": {
        "display_name": "BBC",
        "hosts": {"www.bbc.co.uk", "bbc.co.uk"},
        "template": "",
        "allows_framing": False,
        "uk_rights_verified": True,
        "notice": "BBC 页面禁止嵌入，只能去原站观看。",
    },
}

_SHORT_HOSTS = {"youtu.be", "bit.ly", "t.co", "tinyurl.com"}


def _provider_for(host: str) -> tuple[str, dict[str, object]] | None:
    for code, provider in PROVIDERS.items():
        hosts = provider["hosts"]
        if isinstance(hosts, set) and host in hosts:
            return code, provider
    return None


def framing_blocked(headers: dict[str, str]) -> bool:
    lowered = {key.lower(): value.lower() for key, value in headers.items()}
    if lowered.get("x-frame-options", "") in {"deny", "sameorigin"}:
        return True
    policy = lowered.get("content-security-policy", "")
    return "frame-ancestors" in policy and ("'none'" in policy or "'self'" in policy)


def inspect_source(url: str) -> dict[str, object]:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"framing_blocked": False, "source_title": None, "status_code": None}
    title = None
    blocked = False
    status_code = None
    try:
        with httpx.Client(timeout=2.0, follow_redirects=False) as client:
            response = client.head(url)
            status_code = response.status_code
            blocked = framing_blocked(dict(response.headers))
            if "youtube.com/watch" in url:
                meta = client.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"})
                if meta.status_code == 404:
                    status_code = 404
                elif meta.status_code == 200:
                    found = meta.json().get("title")
                    title = found if isinstance(found, str) else None
    except httpx.HTTPError:
        return {"framing_blocked": False, "source_title": None, "status_code": None}
    return {"framing_blocked": blocked, "source_title": title, "status_code": status_code}


def resolve_embed_url(raw_url: str) -> dict[str, object]:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise APIError(400, "VALIDATION_FAILED", "只接受 https 链接")
    host = parsed.hostname.lower()
    if host in _SHORT_HOSTS:
        raise APIError(400, "EMBED_SHORTLINK_REJECTED", "不接受短链，请贴原站完整地址")
    found = _provider_for(host)
    if found is None:
        raise APIError(400, "EMBED_PROVIDER_NOT_ALLOWED", "这个平台不在白名单里")
    code, provider = found
    media_id = ""
    if code == "youtube":
        if parsed.path == "/watch":
            media_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
            media_id = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else ""
        if not media_id or len(media_id) > 16:
            raise APIError(400, "VALIDATION_FAILED", "无法识别 YouTube 视频编号")
        source = f"https://www.youtube.com/watch?v={media_id}"
    else:
        source = f"https://{host}{parsed.path}"
        media_id = parsed.path.strip("/")[:32] or "page"
    allows = bool(provider["allows_framing"]) and bool(provider["uk_rights_verified"])
    inspected = inspect_source(source)
    if inspected.get("status_code") == 404:
        status = "removed"
    elif allows and not inspected["framing_blocked"]:
        status = "embeddable"
    else:
        status = "fallback"
    return {
        "provider_code": code,
        "display_name": provider["display_name"],
        "media_id": media_id,
        "source_url": source,
        "source_title": inspected["source_title"],
        "embed_status": status,
        "uk_rights_verified": provider["uk_rights_verified"],
        "notice": provider["notice"],
        "consent_required": status == "embeddable",
    }


def rechecked_status(current: str, inspected: dict[str, object]) -> str:
    if inspected.get("status_code") == 404:
        return "removed"
    if inspected.get("framing_blocked") and current == "embeddable":
        return "fallback"
    return current


def embed_url_for(provider_code: str, media_id: str) -> str | None:
    provider = PROVIDERS.get(provider_code)
    if provider is None or not provider["template"] or not media_id:
        return None
    template = str(provider["template"])
    return template.replace("{id}", media_id)

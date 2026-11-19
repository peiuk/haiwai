"""给搜索引擎和聊天软件链接预览用：robots.txt、sitemap.xml，以及每个页面 <head> 里的标题 / 描述 / 分享卡片。

前端是纯浏览器渲染的单页应用，不跑 JS 的爬虫（百度、微信 / WhatsApp 预览）只看得到 index.html。
nginx 用 SSI 把 /api/v1/seo/head/<页面路径> 的结果插进 index.html 的 <head>（见 web/nginx.conf、web/index.html）。
一律按「游客」判断能不能露出：私密房间、待审、下架、封禁的内容只给通用标题，并标 noindex。
"""
import html
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.feed import image_keys_of
from app.models import Channel, Content, User
from app.privacy import can_view_content, viewable

router = APIRouter(prefix="/seo", tags=["seo"])

SITE = "海外圈"
SITE_DESC = "海外华人本地社区：资讯、二手、租房、找工作、同城房间，一个地方都能找到。"
# 登录后才有意义的页面：不让搜索引擎收录
PRIVATE_PREFIXES = ("/admin", "/profile", "/messages", "/publish", "/reset-password", "/search")
# shortcut: 只列最近这么多条帖子；内容超过几万条时改成分页的 sitemap 索引
SITEMAP_LIMIT = 5000


def _base(request: Request) -> str:
    # 前面有 HTTPS / CDN 时 nginx 只看得到 http，所以线上要在 .env 写 PUBLIC_BASE_URL
    return (get_settings().public_base_url.strip() or str(request.base_url)).rstrip("/")


def _clip(text: str | None, limit: int = 150) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _channel_path(channel: Channel) -> str:
    return f"/room/{channel.id}" if channel.kind == "room" else f"/channel/{channel.id}"


def _public_channel(session: Session, channel_id: str) -> Channel | None:
    channel = session.get(Channel, channel_id)
    if channel is None or channel.visibility != "public" or not channel.is_active or channel.is_private:
        return None
    return channel


def _public_content(session: Session, content_id: str) -> Content | None:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None or content.status != "published":
        return None
    return content if can_view_content(session, content, None) else None


def _public_user(session: Session, user_id: str) -> User | None:
    user = session.get(User, user_id)
    return user if user is not None and user.deleted_at is None and user.status == "active" else None


def _page(session: Session, path: str) -> dict[str, str] | None:
    """返回这个页面的标题 / 描述 / 图片 / 类型；None 表示不该被收录。"""
    parts = [p for p in path.split("/") if p]
    if not parts or parts == ["discover"]:
        return {"title": SITE, "desc": SITE_DESC, "type": "website"}
    if parts[0] == "legal":
        return {"title": f"条款与政策 · {SITE}", "desc": SITE_DESC, "type": "website"}
    if len(parts) != 2:
        return None
    kind, item_id = parts
    if kind == "content" and (content := _public_content(session, item_id)):
        keys = image_keys_of(content)
        return {
            "title": f"{_clip(content.title, 60) or _clip(content.body, 30)} · {SITE}",
            "desc": _clip(content.summary) or _clip(content.body) or SITE_DESC,
            "image": f"/api/v1/uploads/{keys[0]}" if keys else "",
            "type": "article",
        }
    if kind in ("channel", "room") and (channel := _public_channel(session, item_id)):
        return {
            "title": f"{channel.name_hans} · {SITE}",
            "desc": _clip(channel.intro) or SITE_DESC,
            "image": f"/api/v1/uploads/{channel.cover_key}" if channel.cover_key else "",
            "type": "website",
        }
    if kind == "user" and (user := _public_user(session, item_id)):
        handle = f" (@{user.handle})" if user.handle else ""
        return {
            "title": f"{user.display_name}{handle} · {SITE}",
            "desc": _clip(user.bio) or f"{user.display_name} 在{SITE}的主页",
            "image": f"/api/v1/uploads/{user.avatar_key}" if user.avatar_key else "",
            "type": "profile",
        }
    return None


@router.get("/head/{path:path}", response_class=HTMLResponse)
def page_head(path: str, request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    path = "/" + path.strip("/")
    base = _base(request)
    page = None if path.startswith(PRIVATE_PREFIXES) else _page(session, path)
    if page is None:
        return HTMLResponse(f'<title>{SITE}</title>\n<meta name="robots" content="noindex">\n')
    esc = lambda value: html.escape(value, quote=True)  # noqa: E731
    url = base + ("" if path == "/" else path)
    image = base + (page.get("image") or "/logo-mark.png")
    tags = [
        f"<title>{esc(page['title'])}</title>",
        f'<meta name="description" content="{esc(page["desc"])}">',
        f'<link rel="canonical" href="{esc(url)}">',
        f'<meta property="og:site_name" content="{SITE}">',
        f'<meta property="og:type" content="{page["type"]}">',
        f'<meta property="og:title" content="{esc(page["title"])}">',
        f'<meta property="og:description" content="{esc(page["desc"])}">',
        f'<meta property="og:url" content="{esc(url)}">',
        f'<meta property="og:image" content="{esc(image)}">',
        f'<meta name="twitter:card" content="{"summary_large_image" if page.get("image") else "summary"}">',
    ]
    return HTMLResponse("\n".join(tags) + "\n")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request) -> PlainTextResponse:
    # 不能挡 /api/：Google 渲染页面时要调接口取内容，挡了就是空白页
    lines = ["User-agent: *", *(f"Disallow: {p}" for p in PRIVATE_PREFIXES), "", f"Sitemap: {_base(request)}/sitemap.xml", ""]
    return PlainTextResponse("\n".join(lines))


@router.get("/sitemap.xml")
def sitemap(request: Request, session: Session = Depends(get_db)) -> Response:
    base = _base(request)
    paths = ["/", "/discover"]
    channels = session.scalars(
        select(Channel)
        .where(Channel.visibility == "public", Channel.is_active.is_(True), Channel.is_private.is_(False))
        .order_by(Channel.created_at)
    ).all()
    paths += [_channel_path(channel) for channel in channels]
    rows = session.execute(
        select(Content.id, Content.published_at, Content.created_at)
        .where(Content.status == "published", Content.deleted_at.is_(None), viewable(None))
        .order_by(Content.created_at.desc())
        .limit(SITEMAP_LIMIT)
    ).all()
    urls = [f"<url><loc>{html.escape(base + p)}</loc></url>" for p in paths]
    urls += [
        f"<url><loc>{html.escape(f'{base}/content/{row.id}')}</loc><lastmod>{(row.published_at or row.created_at).date().isoformat()}</lastmod></url>"
        for row in rows
    ]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
    return Response(body, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})

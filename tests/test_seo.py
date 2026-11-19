"""SEO：页面 <head> 片段、robots.txt、sitemap.xml。私密 / 待审内容不能露出标题，也不能进 sitemap。"""
from app.models import Channel, ChannelItem, Content, User


def seed(client) -> dict[str, str]:
    session = client.session_factory()
    user = User(email="seo@example.com", password_hash="x", display_name="小王", handle="xiaowang", bio="伦敦租房达人")
    news = Channel(code="seo-news", name_hans="英国资讯", name_hant="英國資訊", kind="official_curated", region_code="UK", is_active=True, intro="每天的英国新闻")
    secret = Channel(code="seo-secret", name_hans="秘密房间", name_hant="秘密房間", kind="room", region_code="UK", is_active=True, is_private=True)
    session.add_all([user, news, secret])
    session.flush()
    public = Content(type="post", status="published", author_id=user.id, title='签证 "新规" <速看>', summary="  工签\n门槛上调  ", image_keys_json='["abc.jpg"]')
    hidden = Content(type="post", status="published", author_id=user.id, title="私密房间里的帖子")
    pending = Content(type="post", status="pending", author_id=user.id, title="还没审的帖子")
    session.add_all([public, hidden, pending])
    session.flush()
    session.add_all([ChannelItem(channel_id=news.id, content_id=public.id), ChannelItem(channel_id=secret.id, content_id=hidden.id)])
    session.commit()
    ids = {"user": user.id, "news": news.id, "secret": secret.id, "public": public.id, "hidden": hidden.id, "pending": pending.id}
    session.close()
    return ids


def head(client, path: str) -> str:
    response = client.get(f"/api/v1/seo/head{path}")
    assert response.status_code == 200
    return response.text


def test_public_content_gets_escaped_meta_and_share_card(client):
    ids = seed(client)
    text = head(client, f"/content/{ids['public']}")
    assert "<title>签证 &quot;新规&quot; &lt;速看&gt; · 海外圈</title>" in text
    assert '<meta name="description" content="工签 门槛上调">' in text
    assert f'<link rel="canonical" href="http://testserver/content/{ids["public"]}">' in text
    assert '<meta property="og:image" content="http://testserver/api/v1/uploads/abc.jpg">' in text
    assert "summary_large_image" in text
    assert "noindex" not in text


def test_private_pending_and_unknown_pages_leak_nothing(client):
    ids = seed(client)
    for path in (f"/content/{ids['hidden']}", f"/content/{ids['pending']}", f"/room/{ids['secret']}", "/content/nope", "/admin/users", "/profile"):
        text = head(client, path)
        assert text == '<title>海外圈</title>\n<meta name="robots" content="noindex">\n', path


def test_channel_user_and_home_pages(client):
    ids = seed(client)
    assert "<title>英国资讯 · 海外圈</title>" in head(client, f"/channel/{ids['news']}")
    assert "每天的英国新闻" in head(client, f"/channel/{ids['news']}")
    user_head = head(client, f"/user/{ids['user']}")
    assert "<title>小王 (@xiaowang) · 海外圈</title>" in user_head and "伦敦租房达人" in user_head
    home = head(client, "/")
    assert '<link rel="canonical" href="http://testserver">' in home and "logo-mark.png" in home


def test_public_base_url_setting_wins(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "public_base_url", "https://example.com/")
    assert "Sitemap: https://example.com/sitemap.xml" in client.get("/api/v1/seo/robots.txt").text


def test_robots_and_sitemap(client):
    ids = seed(client)
    robots = client.get("/api/v1/seo/robots.txt").text
    assert "Disallow: /admin" in robots and "Disallow: /api" not in robots
    response = client.get("/api/v1/seo/sitemap.xml")
    assert response.headers["content-type"].startswith("application/xml")
    xml = response.text
    assert f"/content/{ids['public']}</loc>" in xml
    assert f"/channel/{ids['news']}</loc>" in xml
    for hidden in (ids["hidden"], ids["pending"], ids["secret"]):
        assert hidden not in xml

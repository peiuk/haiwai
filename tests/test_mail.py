"""后台发信邮箱（SMTP）设置、测试邮件、忘记密码发重置邮件。不连真的邮件服务器：smtplib 换成记录参数的假对象。"""
import smtplib

import pytest
from sqlalchemy import select

from app.models import AuditLog, PasswordReset, SiteSetting
from tests.test_admin import headers, register
from tests.test_admin_ops import moderator

SECRET = "auth-code-123456"
SETTINGS = {"host": "smtp.example.com", "port": 465, "ssl": True, "user": "noreply@example.com", "password": SECRET,
            "from_name": "海外圈", "site_url": "https://quan.example.com"}
URL = "/api/v1/admin/mail-settings"


class Outbox(list):
    """发出去的每一封：连接方式、主机端口、登录账号密码、有没有 STARTTLS、邮件本身。fail 里放异常就模拟发信失败。"""

    def __init__(self) -> None:
        super().__init__()
        self.fail: list[Exception] = []


@pytest.fixture
def outbox(monkeypatch):
    sent = Outbox()

    def fake(kind: str):
        class Server:
            def __init__(self, host, port, timeout=None):
                self.record = {"kind": kind, "host": host, "port": port, "tls": False}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def starttls(self):
                self.record["tls"] = True

            def login(self, user, password):
                if sent.fail:
                    raise sent.fail[0]
                self.record["login"] = (user, password)

            def send_message(self, message):
                sent.append({**self.record, "to": message["To"], "from": str(message["From"]), "subject": message["Subject"], "text": message.get_content()})

        return Server

    monkeypatch.setattr(smtplib, "SMTP_SSL", fake("ssl"))
    monkeypatch.setattr(smtplib, "SMTP", fake("plain"))
    return sent


def test_only_super_admin_can_configure_and_password_never_comes_back(client, outbox):
    boss = register(client, "boss@example.com", admin=True)
    mod = moderator(client, "mod@example.com")
    user = register(client, "user@example.com")

    for token in (mod, user):
        assert client.get(URL, headers=headers(token)).status_code == 403
        assert client.post(URL, headers=headers(token), json=SETTINGS).status_code == 403
        assert client.post(f"{URL}/test", headers=headers(token), json={"to": "a@example.com"}).status_code == 403
    assert client.get(URL).status_code == 401

    # 没配置时发测试邮件：说清楚原因，不是 500
    assert client.post(f"{URL}/test", headers=headers(boss), json={"to": "a@example.com"}).json()["code"] == "MAIL_NOT_CONFIGURED"

    saved = client.post(URL, headers=headers(boss), json=SETTINGS)
    assert saved.status_code == 200 and saved.json()["password_set"] is True
    shown = client.get(URL, headers=headers(boss))
    assert shown.json() == {**{key: value for key, value in SETTINGS.items() if key != "password"}, "password_set": True}
    assert SECRET not in saved.text + shown.text

    # 授权码留空 = 不改；日志里没有授权码
    assert client.post(URL, headers=headers(boss), json={**SETTINGS, "password": "", "port": 587, "ssl": False}).status_code == 200
    with client.session_factory() as session:
        assert SECRET in session.get(SiteSetting, "mail").value
        assert not [row for row in session.scalars(select(AuditLog)) if SECRET in (row.detail or "")]
        assert session.scalar(select(AuditLog).where(AuditLog.action == "admin.mail.save")) is not None

    # 不走 SSL 直连：先 STARTTLS 再登录
    assert client.post(f"{URL}/test", headers=headers(boss), json={"to": "me@example.com"}).json() == {"sent": True}
    assert outbox[0] | {"text": ""} == {"kind": "plain", "host": "smtp.example.com", "port": 587, "tls": True, "login": ("noreply@example.com", SECRET),
                                        "to": "me@example.com", "from": "海外圈 <noreply@example.com>", "subject": "海外圈测试邮件", "text": ""}

    # 走 SSL 直连
    client.post(URL, headers=headers(boss), json=SETTINGS)
    client.post(f"{URL}/test", headers=headers(boss), json={"to": "me@example.com"})
    assert (outbox[1]["kind"], outbox[1]["port"], outbox[1]["tls"]) == ("ssl", 465, False)

    # 填错的被挡在外面
    for bad in ({"host": "smtp.example.com\nx"}, {"port": 0}, {"user": "not-an-email"}, {"site_url": "javascript:alert(1)"}, {"from_name": "a\nBcc: x@y.z"}):
        assert client.post(URL, headers=headers(boss), json={**SETTINGS, **bad}).status_code == 422, bad


def test_send_failures_are_explained_not_500(client, outbox):
    boss = register(client, "boss@example.com", admin=True)
    client.post(URL, headers=headers(boss), json=SETTINGS)

    outbox.fail.append(smtplib.SMTPAuthenticationError(535, b"Login fail"))
    response = client.post(f"{URL}/test", headers=headers(boss), json={"to": "me@example.com"})
    assert (response.status_code, response.json()["code"]) == (400, "MAIL_AUTH_FAILED")
    assert "授权码" in response.json()["message"] and SECRET not in response.text

    outbox.fail[0] = TimeoutError("timed out")
    response = client.post(f"{URL}/test", headers=headers(boss), json={"to": "me@example.com"})
    assert (response.status_code, response.json()["code"]) == (400, "MAIL_FAILED")
    assert outbox == []


def test_forgot_password_mails_a_working_reset_link(client, outbox):
    boss = register(client, "boss@example.com", admin=True)
    register(client, "user@example.com")
    forgot = "/api/v1/auth/forgot-password"

    # 没配置发信邮箱：告诉用户找管理员
    assert client.post(forgot, json={"email": "user@example.com"}).json()["code"] == "MAIL_NOT_CONFIGURED"
    client.post(URL, headers=headers(boss), json=SETTINGS)

    # 没注册过的邮箱：回一样的结果，但不发信
    assert client.post(forgot, json={"email": "nobody@example.com"}).json() == {"sent": True}
    assert outbox == []

    # 发信失败：对外还是一样的结果，不留凭证，操作日志里有记录
    outbox.fail.append(smtplib.SMTPAuthenticationError(535, b"Login fail"))
    assert client.post(forgot, json={"email": "user@example.com"}).json() == {"sent": True}
    with client.session_factory() as session:
        assert session.scalar(select(PasswordReset)) is None
        assert session.scalar(select(AuditLog).where(AuditLog.action == "account.reset_mail_failed")) is not None
    outbox.fail.clear()

    assert client.post(forgot, json={"email": " User@Example.com "}).json() == {"sent": True}
    assert outbox[0]["to"] == "user@example.com"
    link = next(line for line in outbox[0]["text"].splitlines() if line.startswith("https://quan.example.com/reset-password?token="))
    token = link.split("token=")[1]

    assert client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-password-2"}).json() == {"reset": True}
    assert client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "new-password-2"}).status_code == 200
    # 链接只能用一次
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "password": "another-pw-3"}).status_code == 400

    # 同一个邮箱一小时最多 3 次（没配置的那次也算）
    assert client.post(forgot, json={"email": "user@example.com"}).status_code == 429


def test_register_needs_the_4_digit_code_once_mail_is_configured(client, outbox):
    boss = register(client, "boss@example.com", admin=True)
    send_code = "/api/v1/auth/register-code"
    body = {"email": "new@example.com", "password": "password-1", "display_name": "新人",
            "consents": [{"purpose": "tos", "version": "v1"}, {"purpose": "privacy", "version": "v1"}]}

    # 没配置发信邮箱：不要验证码，照常能注册（不然网站没人能注册）
    assert client.post(send_code, json={"email": "early@example.com"}).json() == {"required": False}
    assert client.post("/api/v1/auth/register", json={**body, "email": "early@example.com"}).status_code == 200

    client.post(URL, headers=headers(boss), json=SETTINGS)
    assert client.post(send_code, json={"email": "boss@example.com"}).json()["code"] == "DUPLICATE_EMAIL"
    assert client.post(send_code, json={"email": " New@Example.com "}).json() == {"required": True}
    code = outbox[-1]["subject"].split()[-1]
    assert len(code) == 4 and code.isdigit() and code in outbox[-1]["text"]
    assert outbox[-1]["to"] == "new@example.com"

    assert client.post("/api/v1/auth/register", json=body).json()["code"] == "INVALID_CODE"  # 没填
    wrong = f"{(int(code) + 1) % 10000:04d}"
    assert client.post("/api/v1/auth/register", json={**body, "code": wrong}).json()["code"] == "INVALID_CODE"
    # 验证码只对发给的那个邮箱有效
    assert client.post("/api/v1/auth/register", json={**body, "email": "other@example.com", "code": code}).json()["code"] == "INVALID_CODE"
    assert client.post("/api/v1/auth/register", json={**body, "code": code}).status_code == 200

    # 猜码限次：同一邮箱 15 分钟内最多试 5 次
    for _ in range(5):
        client.post("/api/v1/auth/register", json={**body, "email": "guess@example.com", "code": "0000"})
    assert client.post("/api/v1/auth/register", json={**body, "email": "guess@example.com", "code": "0000"}).status_code == 429

"""发邮件。SMTP 信息由超级管理员在后台「邮件设置」里填，存在 site_setting 的 mail 一行（JSON）；用标准库 smtplib 发。"""
import json
import smtplib
from email.errors import MessageError
from email.headerregistry import Address
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models import SiteSetting

# shortcut: 授权码明文存库（和两步验证密钥一样），拿到数据库就能用这个邮箱发信；要防这一层得接密钥管理服务。
DEFAULTS: dict[str, object] = {"host": "", "port": 465, "ssl": True, "user": "", "password": "", "from_name": "", "site_url": ""}


def mail_config(session: Session) -> dict[str, object]:
    row = session.get(SiteSetting, "mail")
    return {**DEFAULTS, **(json.loads(row.value) if row else {})}


def mail_ready(config: dict[str, object]) -> bool:
    return bool(config["host"] and config["user"] and config["password"])


def send_mail(config: dict[str, object], to: str, subject: str, text: str) -> None:
    """发一封纯文本邮件。发不出去抛 APIError，带管理员看得懂的原因。"""
    if not mail_ready(config):
        raise APIError(409, "MAIL_NOT_CONFIGURED", "还没有配置发信邮箱")
    host, port = str(config["host"]), int(str(config["port"]))
    try:
        message = EmailMessage()
        message["From"] = Address(str(config["from_name"]), addr_spec=str(config["user"]))
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        with (smtplib.SMTP_SSL if config["ssl"] else smtplib.SMTP)(host, port, timeout=15) as server:
            if not config["ssl"]:
                server.starttls()  # 不走 SSL 直连就必须能升级成加密连接：授权码不在明文连接上发
            server.login(str(config["user"]), str(config["password"]))
            server.send_message(message)
    except smtplib.SMTPAuthenticationError:
        raise APIError(400, "MAIL_AUTH_FAILED", "邮箱账号或授权码不对（QQ / 163 邮箱要填开启 SMTP 时拿到的「授权码」，不是登录密码）") from None
    except smtplib.SMTPRecipientsRefused:
        raise APIError(400, "MAIL_FAILED", "收件地址被邮件服务器拒绝，请检查收件邮箱") from None
    except (smtplib.SMTPException, OSError, ValueError, MessageError) as exc:  # 连不上、超时、证书或端口不对；地址写得不像邮箱
        raise APIError(400, "MAIL_FAILED", f"邮件没发出去，请检查服务器地址、端口、加密方式和邮箱地址（{type(exc).__name__}）") from None

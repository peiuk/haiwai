import hmac
import re
import secrets
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.audit import client_ip, write_audit

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.keywords import clean_city_topic
from app.mail import mail_config, mail_ready, send_mail
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_session_id,
    new_refresh_token,
    read_access_token,
    refresh_expiry,
    verify_password,
)
from app.models import Channel, ChannelSubscription, ConsentRecord, PasswordReset, RateHit, RefreshSession, User, as_utc, utcnow

DEV_PHONE_CODE = "246810"


def throttle(session: Session, key: str, limit: int, window_seconds: int) -> None:
    """窗口内超过 limit 次就拒绝。计数存数据库（rate_hit），多个进程共用、重启不清零。
    会立即提交：失败的尝试（如密码错误）也要算数，所以必须在处理函数开头、还没改别的数据时调用。"""
    key = key[:160]
    now = utcnow()
    session.execute(delete(RateHit).where(RateHit.key == key, RateHit.at < now - timedelta(seconds=window_seconds)))
    hits = session.scalar(select(func.count()).select_from(RateHit).where(RateHit.key == key)) or 0
    if hits >= limit:
        session.commit()
        raise APIError(429, "RATE_LIMITED", "尝试太频繁，请稍后再试")
    session.add(RateHit(key=key, at=now))
    session.commit()


router = APIRouter(prefix="/auth")
bearer = HTTPBearer(auto_error=False)


class ConsentInput(BaseModel):
    # 上限和数据库列宽一致：超了在 PostgreSQL 上会直接 500（SQLite 不检查长度，测试发现不了）
    purpose: str = Field(max_length=48)
    version: str = Field(max_length=32)
    granted: bool = True


class RegisterBody(BaseModel):
    email: str = Field(max_length=255)
    password: str
    display_name: str
    consents: list[ConsentInput] = []
    join_codes: list[str] = []
    script_pref: str = "hans"
    city_code: str | None = None
    handle: str | None = None
    avatar_tone: str = "a"
    code: str = Field(default="", max_length=8)  # 邮箱验证码；后台没配置发信邮箱时不用填

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("邮箱格式不正确")
        return email

    @field_validator("password")
    @classmethod
    def password_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码至少 8 位")
        return value

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, value: str) -> str:
        name = value.strip()
        if not name or len(name) > 40:
            raise ValueError("显示名需要 1 到 40 个字")
        return name

    @field_validator("script_pref")
    @classmethod
    def script_value(cls, value: str) -> str:
        pref = value.strip().lower()
        if pref not in {"hans", "hant"}:
            raise ValueError("script_pref 只能是 hans 或 hant")
        return pref

    @field_validator("handle")
    @classmethod
    def handle_shape(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        handle = value.strip().lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9._]{1,20}", handle):
            raise ValueError("账号名需要 1 到 20 位字母、数字、点或下划线")
        return handle

    @field_validator("avatar_tone")
    @classmethod
    def tone_letter(cls, value: str) -> str:
        tone = value.strip().lower()
        if tone not in {"a", "b", "c", "d", "e", "f"}:
            raise ValueError("头像色不正确")
        return tone

    @field_validator("city_code")
    @classmethod
    def city_label_token(cls, value: str | None) -> str | None:
        return clean_city_topic(value)


def _allocate_handle(session: Session, preferred: str | None, email: str) -> str:
    if preferred:
        taken = session.scalar(select(User.id).where(User.handle == preferred))
        if taken is not None:
            raise APIError(409, "DUPLICATE_HANDLE", "这个账号名已经有人用了")
        return preferred
    base = re.sub(r"[^a-z0-9._]", "", email.split("@")[0].lower())[:12] or "user"
    candidate = base
    number = 0
    while session.scalar(select(User.id).where(User.handle == candidate)) is not None:
        number += 1
        suffix = str(number)
        candidate = f"{base[: 20 - len(suffix)]}{suffix}"
    return candidate


class LoginBody(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


def _load_user(session: Session, credentials: HTTPAuthorizationCredentials | None) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    user_id = read_access_token(credentials.credentials)
    if user_id is None:
        return None
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None or user.status != "active":
        return None
    return user


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_db),
) -> User | None:
    return _load_user(session, credentials)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_db),
) -> User:
    user = _load_user(session, credentials)
    if user is None:
        raise APIError(401, "UNAUTHENTICATED", "请先登录")
    return user


def require_verified_phone(user: User, action: str) -> None:
    """发布类操作前的手机验证门槛；可用 REQUIRE_PHONE_VERIFICATION=false 临时关掉（见 config.py）。"""
    if get_settings().require_phone_verification and not user.phone_verified:
        raise APIError(403, "PHONE_NOT_VERIFIED", f"{action}前需要先验证手机")


ADMIN_SESSION_HOURS = 12  # 后台会话：这么久没操作就要重新登录（每次续期重新计时）


def issue_tokens(session: Session, user_id: str, admin: bool = False) -> dict[str, str]:
    """admin=True 是后台登录发的令牌：访问令牌带后台标记，会话有效期短。"""
    access = create_access_token(user_id, admin)
    raw_refresh = new_refresh_token()
    session.add(
        RefreshSession(
            id=new_refresh_session_id(),
            user_id=user_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=utcnow() + timedelta(hours=ADMIN_SESSION_HOURS) if admin else refresh_expiry(),
            admin=admin,
        )
    )
    return {"access_token": access, "refresh_token": raw_refresh, "token_type": "bearer"}


def lift_expired_suspension(user: User) -> None:
    """限时封禁到期：恢复正常。登录和续期时检查，不用另起定时任务。"""
    if user.status == "suspended" and user.suspended_until is not None and as_utc(user.suspended_until) <= utcnow():
        user.status = "active"
        user.suspended_until = None
        user.suspend_reason = None


def join_channels_by_code(session: Session, user_id: str, codes: list[str]) -> int:
    joined = 0
    for code in codes[:20]:
        trimmed = code.strip().lower()
        if not trimmed:
            continue
        channel = session.scalar(
            select(Channel).where(
                Channel.code == trimmed,
                Channel.is_active.is_(True),
                Channel.visibility == "public",
            )
        )
        if channel is None:
            continue
        exists = session.get(ChannelSubscription, (user_id, channel.id))
        if exists is not None:
            continue
        session.add(ChannelSubscription(user_id=user_id, channel_id=channel.id))
        channel.subscriber_count += 1
        joined += 1
    return joined


CODE_WINDOW_SECONDS = 10 * 60


def email_code(email: str, step: int) -> str:
    """注册验证码 = 密钥对「邮箱 + 时间段」做 HMAC 取 4 位：不用建表存，同一时间段内重发还是同一个码。"""
    digest = hmac.new(get_settings().app_secret_key.encode(), f"register:{email}:{step}".encode(), "sha256").digest()
    return f"{int.from_bytes(digest[:4], 'big') % 10000:04d}"


def email_code_ok(email: str, code: str) -> bool:
    step = int(time.time()) // CODE_WINDOW_SECONDS
    # 收下当前和上一个时间段的码：刚好跨段时发出的码也还能用，有效期 10 到 20 分钟
    return any(secrets.compare_digest(code, email_code(email, s)) for s in (step, step - 1))


class RegisterCodeBody(BaseModel):
    email: str = Field(max_length=255)


@router.post("/register-code")
def register_code(body: RegisterCodeBody, request: Request, session: Session = Depends(get_db)) -> dict[str, bool]:
    """注册前给邮箱发 4 位验证码。后台还没配置发信邮箱时不发，返回 required=False，注册照常不要验证码（不然网站没人能注册）。"""
    email = body.email.strip().lower()
    if "@" not in email.strip("@"):
        raise APIError(400, "INVALID_EMAIL", "邮箱格式不正确")
    config = mail_config(session)
    if not mail_ready(config):
        return {"required": False}
    throttle(session, f"regcode:{email}", limit=5, window_seconds=60 * 60)  # 也防有人拿它往别人邮箱里灌邮件
    throttle(session, f"regcode-ip:{client_ip(request)}", limit=10, window_seconds=60 * 60)
    if session.scalar(select(User.id).where(User.email == email)):
        raise APIError(409, "DUPLICATE_EMAIL", "这个邮箱已经注册")
    code = email_code(email, int(time.time()) // CODE_WINDOW_SECONDS)
    text = f"你好：\n\n你的海外圈注册验证码是 {code}，10 分钟内有效。\n\n不是你本人操作的话，不用理会这封邮件。"
    try:
        send_mail(config, email, f"海外圈注册验证码 {code}", text)
    except APIError:
        raise APIError(503, "MAIL_FAILED", "验证码邮件没发出去，请稍后再试或联系平台管理员") from None
    return {"required": True}


@router.post("/register")
def register(body: RegisterBody, request: Request, session: Session = Depends(get_db)) -> dict[str, object]:
    if mail_ready(mail_config(session)):
        # 验证码先查（且单独限次）：输错几次不该占掉下面「一小时注册 5 个」的名额；5 次 / 15 分钟挡住猜 4 位码
        throttle(session, f"regcode-try:{body.email}", limit=5, window_seconds=15 * 60)
        if not email_code_ok(body.email, body.code.strip()):
            raise APIError(400, "INVALID_CODE", "验证码不正确或已过期")
    # 同一个来源一小时最多注册 5 个号：挡住脚本批量注册（再拿去刷上传、发广告）。
    # 单元测试全部来自同一个地址、每个用例要注册好几个号，所以测试里关掉（有单独的用例打开它测）。
    if not get_settings().testing:
        throttle(session, f"register-ip:{client_ip(request)}", limit=5, window_seconds=60 * 60)
    existing = session.scalar(select(User.id).where(User.email == body.email))
    if existing:
        raise APIError(409, "DUPLICATE_EMAIL", "这个邮箱已经注册")
    granted = {item.purpose for item in body.consents if item.granted}
    if "tos" not in granted or "privacy" not in granted:
        raise APIError(400, "CONSENT_REQUIRED", "需要同意条款和隐私政策")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        handle=_allocate_handle(session, body.handle, body.email),
        avatar_tone=body.avatar_tone,
        city_label=body.city_code,
        script_pref=body.script_pref,
    )
    session.add(user)
    session.flush()
    for item in body.consents:
        session.add(
            ConsentRecord(user_id=user.id, purpose=item.purpose, version=item.version, granted=item.granted)
        )
    joined = join_channels_by_code(session, user.id, body.join_codes)
    write_audit(session, user.id, "account.register", "user", user.id)
    session.flush()
    tokens = issue_tokens(session, user.id)
    session.commit()
    tokens["joined_channels"] = joined
    return tokens


class VerifyPhoneBody(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 8 or len(digits) > 20:
            raise ValueError("请填写有效手机号")
        return f"+{digits}"


@router.post("/verify-phone")
def verify_phone(
    body: VerifyPhoneBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    throttle(session, f"phone:{user.id}", limit=5, window_seconds=15 * 60)
    if get_settings().app_env != "dev":
        # 还没接短信服务商：线上发不出验证码，任何验证码都不可能对。接入前请在 .env 里设
        # REQUIRE_PHONE_VERIFICATION=false，否则没有人能发帖。
        raise APIError(503, "SMS_UNAVAILABLE", "手机验证暂未开通")
    if not secrets.compare_digest(body.code, DEV_PHONE_CODE):
        raise APIError(400, "INVALID_CODE", "验证码不正确")
    taken = session.scalar(select(User.id).where(User.phone == body.phone, User.id != user.id))
    if taken:
        raise APIError(409, "DUPLICATE_PHONE", "这个手机号已经绑定")
    user.phone = body.phone
    user.phone_verified = True
    session.commit()
    return {"phone_verified": True}


@router.post("/login")
def login(body: LoginBody, request: Request, session: Session = Depends(get_db)) -> dict[str, str]:
    # 按「邮箱 + 来源」计数：只按邮箱的话，别人拿你的邮箱乱试 10 次就能让你自己也登不上
    throttle(session, f"login:{body.email}:{client_ip(request)}", limit=10, window_seconds=15 * 60)
    # 同一个来源拿一个密码换着邮箱试（撞库）也要拦；30 次够一家人共用一个网络
    throttle(session, f"login-ip:{client_ip(request)}", limit=30, window_seconds=15 * 60)
    user = session.scalar(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
    if user is None or not verify_password(body.password, user.password_hash):
        raise APIError(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    lift_expired_suspension(user)
    if user.status != "active":  # 密码对了才告诉对方账号被限制，不泄露账号是否存在
        until = f"到 {as_utc(user.suspended_until):%Y-%m-%d %H:%M} (UTC)" if user.suspended_until else ""
        why = f"。原因：{user.suspend_reason}" if user.suspend_reason else ""
        raise APIError(403, "ACCOUNT_SUSPENDED", f"这个账号已被限制{until}，无法登录{why}")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    tokens = issue_tokens(session, user.id)
    session.commit()
    return tokens


RESET_LINK_HOURS = 24


class ForgotPasswordBody(BaseModel):
    email: str = Field(max_length=255)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordBody, request: Request, session: Session = Depends(get_db)) -> dict[str, bool]:
    """自助找回密码：给这个邮箱发一次性重置链接。邮箱注册过没有都回同样的结果，不让人拿这个接口探测账号。"""
    email = body.email.strip().lower()
    throttle(session, f"forgot:{email}", limit=3, window_seconds=60 * 60)  # 也防有人拿它往别人邮箱里灌邮件
    throttle(session, f"forgot-ip:{client_ip(request)}", limit=10, window_seconds=60 * 60)
    config = mail_config(session)
    if not mail_ready(config):
        raise APIError(409, "MAIL_NOT_CONFIGURED", "网站还没有开通邮件找回密码，请联系平台管理员")
    user = session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        return {"sent": True}
    token = new_refresh_token()
    text = (
        f"{user.display_name}，你好：\n\n有人（希望是你本人）在海外圈申请重置这个账号的密码。"
        f"点下面的链接设置新密码，{RESET_LINK_HOURS} 小时内有效，只能用一次：\n\n"
        f"{config['site_url']}/reset-password?token={token}\n\n不是你本人操作的话，不用理会这封邮件，密码不会变。"
    )
    try:
        send_mail(config, user.email, "重置你的海外圈密码", text)
    except APIError as exc:
        # 对外不说发没发出去（说了等于告诉对方这个邮箱注册过）；记进操作日志，管理员在后台看得到
        write_audit(session, user.id, "account.reset_mail_failed", "user", user.id, exc.message)
    else:
        # 发出去了才换凭证：之前没用掉的链接作废，同一时间只有最新的一个有效
        session.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)))
        session.add(PasswordReset(user_id=user.id, token_hash=hash_refresh_token(token), expires_at=utcnow() + timedelta(hours=RESET_LINK_HOURS)))
        write_audit(session, user.id, "account.reset_mail", "user", user.id)
    session.commit()
    return {"sent": True}


class ResetPasswordBody(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=200)


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody, session: Session = Depends(get_db)) -> dict[str, bool]:
    """用一次性链接（邮件里收到的，或管理员生成的）设置新密码。成功后所有设备上的登录都失效，要用新密码重新登录。"""
    digest = hash_refresh_token(body.token.strip())
    throttle(session, f"reset:{digest[:16]}", limit=10, window_seconds=15 * 60)
    row = session.scalar(select(PasswordReset).where(PasswordReset.token_hash == digest))
    if row is None or row.used_at is not None or as_utc(row.expires_at) < utcnow():
        raise APIError(400, "INVALID_RESET_TOKEN", "这个重置链接已经失效，请重新获取")
    user = session.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise APIError(400, "INVALID_RESET_TOKEN", "这个重置链接已经失效，请重新获取")
    user.password_hash = hash_password(body.password)
    row.used_at = utcnow()
    session.execute(delete(RefreshSession).where(RefreshSession.user_id == user.id))
    write_audit(session, user.id, "account.password_reset", "user", user.id)
    session.commit()
    return {"reset": True}


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh_session(body: RefreshBody, session: Session = Depends(get_db)) -> dict[str, str]:
    digest = hash_refresh_token(body.refresh_token.strip())
    row = session.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
    if row is None:
        raise APIError(401, "INVALID_REFRESH", "登录已失效，请重新登录")
    if as_utc(row.expires_at) < utcnow():
        session.delete(row)
        session.commit()
        raise APIError(401, "INVALID_REFRESH", "登录已失效，请重新登录")
    user = session.get(User, row.user_id)
    if user is not None:
        lift_expired_suspension(user)
    if user is None or user.deleted_at is not None or user.status != "active":
        session.delete(row)
        session.commit()
        raise APIError(401, "INVALID_REFRESH", "登录已失效，请重新登录")
    session.delete(row)
    # 后台会话续期后仍是后台会话；管理员权限被撤销的，续出来的只是普通令牌
    tokens = issue_tokens(session, user.id, admin=row.admin and user.is_admin)
    session.commit()
    return tokens


class LogoutBody(BaseModel):
    refresh_token: str


@router.post("/logout")
def logout(body: LogoutBody, session: Session = Depends(get_db)) -> dict[str, bool]:
    digest = hash_refresh_token(body.refresh_token.strip())
    row = session.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
    if row is not None:
        session.delete(row)
        session.commit()
    return {"logged_out": True}

import re
import secrets
import time
from collections import deque
from datetime import timezone

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import write_audit

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.keywords import clean_city_topic
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
from app.models import Channel, ChannelSubscription, ConsentRecord, RefreshSession, User, utcnow

DEV_PHONE_CODE = "246810"

# shortcut: 计数放在每个进程的内存里，2 个 worker 各算各的、重启后清零；
# 需要严格限流或按 IP 限制注册时，换成 Redis 等共享存储，并让反向代理传真实客户端 IP。
_attempts: dict[str, deque[float]] = {}


def throttle(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    if len(_attempts) > 50_000:  # 键只增不减会吃内存：超过上限时清掉一小时内没动静的
        for stale in [name for name, hits in _attempts.items() if not hits or now - hits[-1] > 3600]:
            del _attempts[stale]
    hits = _attempts.setdefault(key, deque())
    while hits and now - hits[0] > window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        raise APIError(429, "RATE_LIMITED", "尝试太频繁，请稍后再试")
    hits.append(now)


def _aware_datetime(value) -> object:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

router = APIRouter(prefix="/auth")
bearer = HTTPBearer(auto_error=False)


class ConsentInput(BaseModel):
    purpose: str
    version: str
    granted: bool = True


class RegisterBody(BaseModel):
    email: str
    password: str
    display_name: str
    consents: list[ConsentInput] = []
    join_codes: list[str] = []
    script_pref: str = "hans"
    city_code: str | None = None
    handle: str | None = None
    avatar_tone: str = "a"

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


def issue_tokens(session: Session, user_id: str) -> dict[str, str]:
    access = create_access_token(user_id)
    raw_refresh = new_refresh_token()
    session.add(
        RefreshSession(
            id=new_refresh_session_id(),
            user_id=user_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_expiry(),
        )
    )
    return {"access_token": access, "refresh_token": raw_refresh, "token_type": "bearer"}


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


@router.post("/register")
def register(body: RegisterBody, session: Session = Depends(get_db)) -> dict[str, object]:
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
        if len(digits) < 8:
            raise ValueError("请填写有效手机号")
        return f"+{digits}"


@router.post("/verify-phone")
def verify_phone(
    body: VerifyPhoneBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    throttle(f"phone:{user.id}", limit=5, window_seconds=15 * 60)
    if get_settings().app_env != "dev" or not secrets.compare_digest(body.code, DEV_PHONE_CODE):
        raise APIError(400, "INVALID_CODE", "验证码不正确")
    taken = session.scalar(select(User.id).where(User.phone == body.phone, User.id != user.id))
    if taken:
        raise APIError(409, "DUPLICATE_PHONE", "这个手机号已经绑定")
    user.phone = body.phone
    user.phone_verified = True
    session.commit()
    return {"phone_verified": True}


@router.post("/login")
def login(body: LoginBody, session: Session = Depends(get_db)) -> dict[str, str]:
    throttle(f"login:{body.email}", limit=10, window_seconds=15 * 60)
    user = session.scalar(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
    if user is None or not verify_password(body.password, user.password_hash):
        raise APIError(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    tokens = issue_tokens(session, user.id)
    session.commit()
    return tokens


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh_session(body: RefreshBody, session: Session = Depends(get_db)) -> dict[str, str]:
    digest = hash_refresh_token(body.refresh_token.strip())
    row = session.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
    if row is None:
        raise APIError(401, "INVALID_REFRESH", "登录已失效，请重新登录")
    if _aware_datetime(row.expires_at) < utcnow():
        session.delete(row)
        session.commit()
        raise APIError(401, "INVALID_REFRESH", "登录已失效，请重新登录")
    user = session.get(User, row.user_id)
    if user is None or user.deleted_at is not None or user.status != "active":
        session.delete(row)
        session.commit()
        raise APIError(401, "INVALID_REFRESH", "登录已失效，请重新登录")
    session.delete(row)
    tokens = issue_tokens(session, user.id)
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

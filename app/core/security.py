import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.models import new_id


# OWASP 2023 对 PBKDF2-SHA256 的建议轮数。轮数写进哈希字符串，以后再调高也不会让旧密码失效。
PBKDF2_ITERATIONS = 600_000
_LEGACY_ITERATIONS = 120_000  # 旧格式 pbkdf2_sha256$salt$digest 没记录轮数，固定是这个值


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _parse_hash(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if len(parts) == 3 and parts[0] == "pbkdf2_sha256":
        return _LEGACY_ITERATIONS, parts[1], parts[2]
    if len(parts) == 4 and parts[0] == "pbkdf2_sha256" and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse_hash(stored)
    if parsed is None:
        return False
    rounds, salt, digest = parsed
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds).hex()
    return secrets.compare_digest(check, digest)


def needs_rehash(stored: str) -> bool:
    """登录成功后用：旧格式或轮数偏低时，顺手用当前设置重新哈希。"""
    parsed = _parse_hash(stored)
    return parsed is None or parsed[0] < PBKDF2_ITERATIONS


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def read_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def refresh_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)


def new_refresh_session_id() -> str:
    return new_id()

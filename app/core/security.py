import base64
import hashlib
import hmac
import secrets
import struct
import time
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


def create_access_token(user_id: str, admin: bool = False) -> str:
    """admin=True 只在后台登录（过了两步验证）时给：后台接口只认带这个标记的令牌。"""
    settings = get_settings()
    payload: dict[str, object] = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    if admin:
        payload["adm"] = True
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def token_is_admin(token: str) -> bool:
    try:
        payload = jwt.decode(token, get_settings().app_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return False
    return payload.get("adm") is True


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def totp_code(secret: str, step: int) -> str:
    """RFC 6238：30 秒一个 6 位数字，和手机上的验证器 App（Google Authenticator 等）算法一致。"""
    digest = hmac.new(base64.b32decode(secret), struct.pack(">Q", step), "sha1").digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{number % 1_000_000:06d}"


def verify_totp(secret: str, code: str) -> bool:
    # shortcut: 同一个验证码在 30 秒内可以重复用；要防重放就记下每个账号上次用过的时间片。
    step = int(time.time()) // 30
    given = code.strip().replace(" ", "")
    # 前后各放宽一个时间片，容忍手机和服务器的时钟差
    return any(secrets.compare_digest(totp_code(secret, step + drift), given) for drift in (-1, 0, 1))


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

"""管理后台的运营工具：两步验证、审核认领、批量处理、敏感词、导出、用户数据请求、运行状况。

基础的列表和单条操作在 admin.py，频道和国家在 admin_channels.py。
"""
import base64
import binascii
import csv
import io
import os
from datetime import timedelta
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.v1.admin import (
    CLAIM_MINUTES,
    Reasoned,
    TakedownBody,
    _names,
    active_claims,
    require_admin,
    require_super,
    set_content_status,
)
from app.api.v1.me import erase_account, export_account
from app.api.v1.uploads import _s3, upload_root
from app.core.audit import recent_server_errors, write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.security import new_totp_secret, verify_totp
from app.models import AuditLog, BlockedTerm, Content, ModerationCase, ReviewClaim, User, utcnow

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


# ---- 当前管理员、两步验证 ----


@router.get("/me")
def admin_me(admin: User = Depends(require_admin)) -> dict[str, object]:
    return {"user_id": admin.id, "display_name": admin.display_name, "is_super": admin.is_super, "two_factor": bool(admin.totp_secret)}


@router.post("/totp/setup")
def totp_setup(admin: User = Depends(require_admin)) -> dict[str, str]:
    """生成一个新密钥给验证器 App 扫 / 手输。这一步还没生效，要用 App 上的验证码调 enable 确认。"""
    secret = new_totp_secret()
    label = quote(f"海外圈后台:{admin.email}")
    return {"secret": secret, "uri": f"otpauth://totp/{label}?secret={secret}&issuer={quote('海外圈后台')}"}


class TotpEnableBody(BaseModel):
    secret: str = Field(min_length=16, max_length=64)
    code: str = Field(min_length=6, max_length=8)


@router.post("/totp/enable")
def totp_enable(body: TotpEnableBody, admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict[str, bool]:
    try:
        base64.b32decode(body.secret)
    except (binascii.Error, ValueError):
        raise APIError(422, "VALIDATION_FAILED", "密钥格式不对，请重新开始设置") from None
    if not verify_totp(body.secret, body.code):
        raise APIError(400, "TOTP_INVALID", "验证码不正确。请确认手机时间是自动设置的，然后再试")
    admin.totp_secret = body.secret
    write_audit(session, admin.id, "admin.totp.enable", "user", admin.id)
    session.commit()
    return {"two_factor": True}


class TotpCodeBody(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/totp/disable")
def totp_disable(body: TotpCodeBody, admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict[str, bool]:
    """关闭两步验证要再输一次验证码：手机丢了的话让超级管理员在服务器上跑 python -m app.make_admin <邮箱> --reset-2fa。"""
    if not admin.totp_secret:
        raise APIError(409, "NO_CHANGE", "还没有开启两步验证")
    if not verify_totp(admin.totp_secret, body.code):
        raise APIError(400, "TOTP_INVALID", "验证码不正确")
    admin.totp_secret = None
    write_audit(session, admin.id, "admin.totp.disable", "user", admin.id)
    session.commit()
    return {"two_factor": False}


# ---- 审核认领 ----


class ClaimBody(BaseModel):
    target_type: Literal["content", "comment", "channel", "case"]
    target_id: str = Field(min_length=1, max_length=36)


@router.post("/claims")
def claim(body: ClaimBody, admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict[str, bool]:
    """开始处理队列里的一条之前先认领：别人正在处理就拒绝，免得两个人同时审同一条。"""
    holder = active_claims(session).get((body.target_type, body.target_id))
    if holder and holder != admin.id:
        name = _names(session, [holder]).get(holder, "其他管理员")
        raise APIError(409, "CLAIMED", f"{name} 正在处理这一条，{CLAIM_MINUTES} 分钟内没处理完你就可以接手")
    # 过期的认领顺手清掉，表不会越攒越大
    session.execute(delete(ReviewClaim).where(ReviewClaim.claimed_at < utcnow() - timedelta(minutes=CLAIM_MINUTES)))
    session.merge(ReviewClaim(target_type=body.target_type, target_id=body.target_id, admin_id=admin.id, claimed_at=utcnow()))
    session.commit()
    return {"claimed": True}


# ---- 批量处理 ----


class BatchBody(Reasoned):
    ids: list[str] = Field(min_length=1, max_length=100)
    action: Literal["approve", "reject", "remove"]


@router.post("/contents/batch")
def batch_contents(body: BatchBody, admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict[str, object]:
    """一次处理多条内容：通过 / 拒绝（待审的）或下架。逐条走和单条一样的规则，某条不行不影响其他的。"""
    from app.api.v1 import moderation  # 放在函数里导入：moderation 模块本身要导入 admin.require_admin

    done = 0
    failed: list[dict[str, str]] = []
    for content_id in dict.fromkeys(body.ids):  # 去重，保持顺序
        try:
            if body.action == "remove":
                set_content_status(content_id, TakedownBody(action="remove", reason=body.reason), admin, session)
            else:
                moderation.decide(content_id, moderation.DecisionBody(decision=body.action, note=body.reason), admin, session)
            done += 1
        except APIError as exc:
            session.rollback()
            failed.append({"content_id": content_id, "message": exc.message})
    return {"done": done, "failed": failed}


# ---- 敏感词 / 链接黑名单 ----


class TermBody(BaseModel):
    term: str = Field(min_length=2, max_length=64)


@router.get("/terms")
def list_terms(session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    rows = session.scalars(select(BlockedTerm).order_by(BlockedTerm.created_at.desc())).all()
    return {"items": [{"term": row.term, "created_at": row.created_at} for row in rows]}


@router.post("/terms")
def add_term(body: TermBody, admin: User = Depends(require_super), session: Session = Depends(get_db)) -> dict[str, str]:
    term = body.term.strip().lower()
    if len(term) < 2:
        raise APIError(422, "VALIDATION_FAILED", "至少 2 个字：太短的词会把正常内容也拦下来")
    if session.get(BlockedTerm, term) is not None:
        raise APIError(409, "NO_CHANGE", "这个词已经在名单里")
    session.add(BlockedTerm(term=term))
    write_audit(session, admin.id, "admin.term.add", "term", None, term)
    session.commit()
    return {"term": term}


@router.post("/terms/delete")
def delete_term(body: TermBody, admin: User = Depends(require_super), session: Session = Depends(get_db)) -> dict[str, bool]:
    row = session.get(BlockedTerm, body.term.strip().lower())
    if row is None:
        raise APIError(404, "TERM_NOT_FOUND", "名单里没有这个词")
    session.delete(row)
    write_audit(session, admin.id, "admin.term.delete", "term", None, row.term)
    session.commit()
    return {"deleted": True}


# ---- 导出 ----

EXPORT_ROWS = 10_000  # shortcut: 一次最多导出这么多行、整份放在内存里；数据更多时改成按时间段分批或流式输出。


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    # 用 Excel 打开时，以这些符号开头的格子会被当成公式执行；前面加个单引号让它只是文字
    return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text


def _csv(filename: str, header: list[str], rows: list[list[object]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows([_cell(value) for value in row] for row in rows)
    # 开头的 BOM 让 Excel 按 UTF-8 打开，中文不乱码
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{kind}")
def export_table(
    kind: Literal["users", "contents", "audit"],
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> Response:
    """把用户、内容或操作日志导出成 CSV（最近的 1 万行）。导出本身记入操作日志。"""
    write_audit(session, admin.id, "admin.export", "table", None, kind)
    session.commit()
    stamp = f"{utcnow():%Y%m%d-%H%M}"
    if kind == "users":
        users = session.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()).limit(EXPORT_ROWS)).all()
        return _csv(
            f"users-{stamp}.csv",
            ["用户 ID", "名字", "账号名", "邮箱", "状态", "管理员", "手机已验证", "注册时间"],
            [
                [row.id, row.display_name, row.handle, row.email, row.status, "是" if row.is_admin else "", "是" if row.phone_verified else "", row.created_at]
                for row in users
            ],
        )
    if kind == "contents":
        contents = session.scalars(select(Content).order_by(Content.created_at.desc()).limit(EXPORT_ROWS)).all()
        names = _names(session, [row.author_id for row in contents])
        return _csv(
            f"contents-{stamp}.csv",
            ["内容 ID", "标题", "类型", "状态", "作者", "浏览", "发布时间"],
            [
                [row.id, row.title, row.type, row.status, names.get(row.author_id or "", row.source_name or ""), row.view_count or 0, row.created_at]
                for row in contents
            ],
        )
    logs = session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(EXPORT_ROWS)).all()
    names = _names(session, [row.actor_id for row in logs])
    return _csv(
        f"audit-{stamp}.csv",
        ["时间", "操作人", "动作", "对象类型", "对象 ID", "备注", "IP", "浏览器"],
        [
            [row.created_at, names.get(row.actor_id or "", ""), row.action, row.target_type, row.target_id, row.detail, row.ip, row.user_agent]
            for row in logs
        ],
    )


# ---- 用户数据请求（数据保护法下用户有权拿到、删除自己的数据）----


def _target(session: Session, user_id: str) -> User:
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    return target


@router.get("/users/{user_id}/export")
def export_user_data(user_id: str, admin: User = Depends(require_super), session: Session = Depends(get_db)) -> dict[str, object]:
    """这个用户的全部个人数据，内容和用户自己在前台「导出我的数据」拿到的一样。"""
    target = _target(session, user_id)
    write_audit(session, admin.id, "admin.user.export", "user", target.id)
    session.commit()
    return export_account(target, session)


class EraseBody(Reasoned):
    confirm_email: str  # 原样输入对方的邮箱，防止点错人


@router.post("/users/{user_id}/erase")
def erase_user(user_id: str, body: EraseBody, admin: User = Depends(require_super), session: Session = Depends(get_db)) -> dict[str, str]:
    """替用户注销账号：抹掉个人资料、下架帖子、删掉上传的文件，不能恢复。和用户自己在前台注销的效果一样。"""
    target = _target(session, user_id)
    if target.is_admin:
        raise APIError(409, "CANNOT_SUSPEND_ADMIN", "不能注销管理员；先撤销对方的管理员权限")
    if body.confirm_email.strip().lower() != target.email:
        raise APIError(422, "VALIDATION_FAILED", "输入的邮箱不一致，没有注销")
    write_audit(session, admin.id, "admin.user.erase", "user", target.id, body.note)  # 不记名字和邮箱：注销就是要抹掉它们
    return erase_account(target, session)


# ---- 运行状况 ----


@router.get("/health")
def health(session: Session = Depends(get_db)) -> dict[str, object]:
    """概览页的运行状况：存储能不能用、近一小时出了多少次服务器错误、最早一条没处理的待办等了多久。"""
    remote = _s3()
    try:
        if remote is None:
            storage_ok = os.access(upload_root(), os.W_OK)
        else:
            remote[0].head_bucket(Bucket=remote[1])
            storage_ok = True
    except Exception:  # 连不上、密钥不对、桶不存在：都算不可用
        storage_ok = False
    oldest_pending = session.scalar(
        select(Content.created_at).where(Content.status == "pending", Content.deleted_at.is_(None)).order_by(Content.created_at).limit(1)
    )
    oldest_case = session.scalar(
        select(ModerationCase.created_at).where(ModerationCase.status == "open").order_by(ModerationCase.created_at).limit(1)
    )
    return {
        "storage": "对象存储" if remote else "本地磁盘",
        "storage_ok": storage_ok,
        "server_errors_1h": recent_server_errors(),
        "oldest_pending": oldest_pending,
        "oldest_case": oldest_case,
    }

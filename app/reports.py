from fastapi import Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from app.api.v1.auth import throttle
from app.core.audit import client_ip
from app.models import ModerationCase, User

REASONS = {
    "scam": "诈骗、虚假信息或可疑交易",
    "harass": "骚扰、仇恨或人身攻击",
    "sexual": "色情内容或未成年人风险",
    "ip": "侵犯版权或盗用内容",
    "privacy": "泄露他人隐私（住址、证件、电话）",
    "other": "其他问题",
}
SLA = "违法内容 24 小时内处理"


class ReportBody(BaseModel):
    reason: str
    detail: str = ""

    @field_validator("reason")
    @classmethod
    def known_reason(cls, value: str) -> str:
        if value not in REASONS:
            raise ValueError("举报原因不正确")
        return value

    @model_validator(mode="after")
    def other_needs_detail(self) -> "ReportBody":
        note = self.detail.strip()
        if self.reason == "other" and len(note) < 4:
            raise ValueError("请补充至少 4 个字的说明")
        if len(note) > 300:
            raise ValueError("补充说明最多 300 个字")
        self.detail = note
        return self


def limit_reports(session: Session, request: Request, user: User | None) -> None:
    """举报限流：登录用户按账号、游客按来源 IP，一小时 10 次。不然脚本对每个用户、每条帖子各举报一次，真举报就被埋掉了。"""
    throttle(session, f"report:{user.id if user else client_ip(request)}", limit=10, window_seconds=60 * 60)


def report_receipt(case: ModerationCase) -> dict[str, str]:
    return {
        "case_id": case.id,
        "status": case.status,
        "reason": case.reason,
        "reason_text": REASONS[case.reason],
        "sla": SLA,
    }

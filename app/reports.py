from pydantic import BaseModel, field_validator, model_validator

from app.models import ModerationCase

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


def report_receipt(case: ModerationCase) -> dict[str, str]:
    return {
        "case_id": case.id,
        "status": case.status,
        "reason": case.reason,
        "reason_text": REASONS[case.reason],
        "sla": SLA,
    }

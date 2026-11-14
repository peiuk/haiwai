from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    session: Session,
    actor_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> None:
    session.add(
        AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id)
    )

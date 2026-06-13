import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.models import AuditLog, User


def client_ip(request: Request | None) -> str:
    if not request:
        return ""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    return forwarded_for.split(",", 1)[0].strip() or (request.client.host if request.client else "")


def user_agent(request: Request | None) -> str:
    if not request:
        return ""
    return request.headers.get("user-agent", "")[:255]


def write_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor: User | None = None,
    request: Request | None = None,
    before: Any | None = None,
    after: Any | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            before_json=json.dumps(before or {}, default=str),
            after_json=json.dumps(after or {}, default=str),
        )
    )

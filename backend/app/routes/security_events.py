from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.security import SecurityEvent
from app.security import require_admin
from app.serializers import serialize_security_event

router = APIRouter(prefix="/api/admin/security-events", tags=["admin-security-events"])


@router.get("")
def list_security_events(
    _: object = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=500),
    severity: str | None = Query(default=None, pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    event_type: str | None = Query(default=None, alias="eventType", max_length=100),
    db: Session = Depends(get_db),
):
    query = db.query(SecurityEvent)
    if severity:
        query = query.filter(SecurityEvent.severity == severity.upper())
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)

    events = query.order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc()).limit(limit).all()
    return [serialize_security_event(event) for event in events]


@router.get("/summary")
def security_event_summary(
    _: object = Depends(require_admin),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    base_query = db.query(SecurityEvent).filter(SecurityEvent.created_at >= since)

    severity_rows = (
        db.query(SecurityEvent.severity, func.count(SecurityEvent.id))
        .filter(SecurityEvent.created_at >= since)
        .group_by(SecurityEvent.severity)
        .all()
    )
    event_type_rows = (
        db.query(SecurityEvent.event_type, func.count(SecurityEvent.id))
        .filter(SecurityEvent.created_at >= since)
        .group_by(SecurityEvent.event_type)
        .order_by(func.count(SecurityEvent.id).desc())
        .limit(10)
        .all()
    )

    return {
        "windowHours": hours,
        "total": base_query.count(),
        "bySeverity": {severity: count for severity, count in severity_rows},
        "topEventTypes": [{"eventType": event_type, "count": count} for event_type, count in event_type_rows],
    }

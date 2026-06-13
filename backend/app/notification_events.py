from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Notification


def add_notification(
    db: Session,
    *,
    user_id: int | None,
    title: str,
    message: str,
    type: str = "info",
    entity_type: str = "",
    entity_id: str = "",
    created_by_user_id: int | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        created_by_user_id=created_by_user_id,
        title=title.strip()[:140],
        message=message.strip()[:700],
        type=type,
        entity_type=entity_type.strip()[:80],
        entity_id=entity_id.strip()[:80],
    )
    db.add(notification)
    return notification


def add_admin_notification(
    db: Session,
    *,
    title: str,
    message: str,
    type: str = "warning",
    entity_type: str = "",
    entity_id: str = "",
    created_by_user_id: int | None = None,
) -> Notification:
    return add_notification(
        db,
        user_id=None,
        title=title,
        message=message,
        type=type,
        entity_type=entity_type,
        entity_id=entity_id,
        created_by_user_id=created_by_user_id,
    )


def mark_admin_notifications_read(db: Session, *, entity_type: str, entity_id: str) -> None:
    (
        db.query(Notification)
        .filter(
            Notification.user_id.is_(None),
            Notification.entity_type == entity_type,
            Notification.entity_id == entity_id,
            Notification.read_at.is_(None),
        )
        .update({Notification.read_at: datetime.utcnow()}, synchronize_session=False)
    )

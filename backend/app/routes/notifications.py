from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.access import is_admin
from app.database import get_db
from app.models.models import Notification, User
from app.schemas import NotificationCreate
from app.security import require_admin, require_user
from app.serializers import serialize_notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/api/admin/notifications", tags=["admin-notifications"])


def _notification_query(db: Session):
    return (
        db.query(Notification)
        .options(joinedload(Notification.user), joinedload(Notification.created_by))
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )


@router.get("")
def list_notifications(user: User = Depends(require_user), db: Session = Depends(get_db)):
    query = _notification_query(db)
    if is_admin(user):
        query = query.filter(or_(Notification.user_id == user.id, Notification.user_id.is_(None)))
    else:
        query = query.filter(Notification.user_id == user.id)
    return [serialize_notification(notification) for notification in query.limit(100).all()]


@router.patch("/{notification_id}/read")
def mark_notification_read(notification_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if is_admin(user):
        if notification.user_id not in (None, user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update notifications addressed to you")
    elif notification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own notifications")

    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return serialize_notification(notification)


@admin_router.post("", status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    recipient = db.get(User, payload.user_id)
    if not recipient or not recipient.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active recipient user not found")

    notification = Notification(
        user_id=recipient.id,
        created_by_user_id=admin.id,
        title=payload.title.strip(),
        message=payload.message.strip(),
        type=payload.type,
        entity_type=payload.entity_type.strip(),
        entity_id=payload.entity_id.strip(),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    write_audit_log(
        db,
        action="admin.notification_created",
        entity_type="notification",
        entity_id=str(notification.id),
        actor=admin,
        request=request,
        after=serialize_notification(notification),
    )
    db.commit()
    return serialize_notification(notification)

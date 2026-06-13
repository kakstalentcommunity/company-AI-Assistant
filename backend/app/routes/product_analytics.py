import logging

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProductAnalyticsEventCreate
from app.security import require_admin, require_user
from app.serializers import serialize_product_analytics_event
from app.services.product_analytics import build_product_analytics_dashboard, persist_event

router = APIRouter(prefix="/api/analytics", tags=["product-analytics"])
admin_router = APIRouter(prefix="/api/admin/analytics", tags=["admin-product-analytics"])
logger = logging.getLogger("umojafunds.analytics")


@router.post("/events", status_code=status.HTTP_201_CREATED)
def track_product_event(
    payload: ProductAnalyticsEventCreate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        event = persist_event(db, user.id, payload)
        return serialize_product_analytics_event(event)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to persist product analytics event")
    except Exception:
        db.rollback()
        logger.exception("Unexpected product analytics tracking failure")

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "id": 0,
            "stored": False,
            "detail": "Analytics event accepted but was not persisted.",
        },
    )


@admin_router.get("/dashboard")
def product_usage_dashboard(
    _: object = Depends(require_admin),
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
):
    return build_product_analytics_dashboard(db, days)


@admin_router.get("/schema")
def product_analytics_schema(_: object = Depends(require_admin)):
    return {
        "tables": [
            "product_analytics_events",
            "product_usage_daily_metrics",
            "product_analytics_alerts",
            "product_analytics_insights",
        ],
        "eventContract": {
            "sessionId": "Stable client session id",
            "eventName": "feature_used, session_end, loan_application_step, error",
            "feature": "balance_check, loans, chatbot, statements, general",
            "funnelName": "loan_application for loan funnel events",
            "funnelStep": "started, eligibility_checked, documents_uploaded, guarantors_added, submitted, approved",
            "device": "Android, iOS, Web, USSD",
            "durationSeconds": "Optional session or action duration",
            "properties": "Additional JSON metadata without sensitive PII",
        },
    }

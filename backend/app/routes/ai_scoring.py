import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.access import ensure_member_access
from app.database import get_db
from app.models.models import LoanScoreEvent
from app.schemas import LoanScoreRequest
from app.security import require_user
from app.services.scoring import calculate_score, score_member_loan

router = APIRouter(prefix="/api/ai", tags=["ai-scoring"])


def _json_value(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except json.JSONDecodeError:
        return fallback


def _int_value(value: Any) -> int:
    if isinstance(value, Decimal):
        return int(value)
    return int(value or 0)


def _serialize_score_event(event: LoanScoreEvent) -> dict:
    created_at = getattr(event, "created_at")
    return {
        "id": getattr(event, "id"),
        "memberId": str(getattr(event, "member_id")),
        "loanAmount": _int_value(getattr(event, "requested_amount")),
        "loanType": str(getattr(event, "loan_type")),
        "composite": _int_value(getattr(event, "composite")),
        "repaymentLikelihood": _int_value(getattr(event, "repayment_likelihood")),
        "defaultRisk": str(getattr(event, "default_risk")),
        "recommendation": str(getattr(event, "recommendation")),
        "modelVersion": str(getattr(event, "model_version")),
        "dimensions": _json_value(getattr(event, "dimensions_json"), []),
        "keyRisks": _json_value(getattr(event, "key_risks_json"), []),
        "keyStrengths": _json_value(getattr(event, "key_strengths_json"), []),
        "scoredAt": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
    }


@router.post("/score")
def ai_score(
    payload: LoanScoreRequest | dict,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    if isinstance(payload, dict):
        member_id = payload.get("memberId") or payload.get("member_id")
        loan_amount = payload.get("loanAmount") or payload.get("loan_amount")
        loan_type = payload.get("loanType") or payload.get("loan_type") or "Business"
        persist = bool(payload.get("persist", True))
    else:
        member_id = payload.member_id
        loan_amount = payload.loan_amount
        loan_type = payload.loan_type
        persist = payload.persist

    if not member_id and loan_amount is None:
        score = calculate_score(payload if isinstance(payload, dict) else {**payload.model_dump(), **(payload.model_extra or {})})
        risk = "LOW" if score >= 80 else "MEDIUM" if score >= 60 else "HIGH"
        return {"score": score, "risk": risk, "approved": score >= 60}

    if not member_id or loan_amount is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="memberId and loanAmount are required for loan scoring",
        )

    ensure_member_access(db, user, str(member_id))

    try:
        return score_member_loan(
            db=db,
            member_id=member_id,
            loan_amount=float(loan_amount),
            loan_type=loan_type,
            persist=persist,
        )
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/score-history/{member_id}")
def score_history(member_id: str, user=Depends(require_user), db: Session = Depends(get_db)):
    ensure_member_access(db, user, member_id)
    events = (
        db.query(LoanScoreEvent)
        .filter(LoanScoreEvent.member_id == member_id)
        .order_by(LoanScoreEvent.created_at.desc(), LoanScoreEvent.id.desc())
        .limit(25)
        .all()
    )

    return [_serialize_score_event(event) for event in events]

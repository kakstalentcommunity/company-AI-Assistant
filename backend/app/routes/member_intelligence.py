from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_admin
from app.services.member_intelligence import get_member_intelligence

router = APIRouter(prefix="/api/member-intelligence", tags=["member-intelligence"])


@router.get("")
def lookup_member_intelligence(
    q: str,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return get_member_intelligence(db, q)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connected database is unavailable or timed out while reading cr_bo_accounts/cr_loans",
        ) from exc

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.access import ensure_member_access, is_admin, member_for_user
from app.database import get_db
from app.models.models import Loan, Member
from app.pagination import page_query, paginate, per_page_query
from app.schemas import LoanCreate, LoanUpdate
from app.security import require_admin, require_user
from app.serializers import serialize_loan

router = APIRouter(prefix="/api/loans", tags=["loans"])


def _sync_member_loan_total(db: Session, member_id: str) -> None:
    member = db.get(Member, member_id)
    if not member:
        return

    loans = db.query(Loan).filter(Loan.member_id == member_id).all()
    member.loans = sum((loan.balance or Decimal("0") for loan in loans), Decimal("0"))


@router.get("")
def get_loans(
    page: int | None = page_query(),
    per_page: int | None = per_page_query(),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    query = db.query(Loan).options(joinedload(Loan.member)).order_by(Loan.issued.desc(), Loan.id.desc())
    if not is_admin(user):
        member = member_for_user(db, user)
        query = query.filter(Loan.member_id == member.id)

    if page is not None and per_page is not None:
        return paginate(query, page, per_page, serialize_loan)

    return [serialize_loan(loan) for loan in query.all()]


@router.get("/{loan_id}")
def get_loan(loan_id: str, user=Depends(require_user), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    ensure_member_access(db, user, str(loan.member_id))
    return serialize_loan(loan)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_loan(payload: LoanCreate, request: Request, admin=Depends(require_admin), db: Session = Depends(get_db)):
    member = db.get(Member, payload.member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    loan_id = payload.id or f"LN-{db.query(Loan).count() + 1:06d}"
    if db.get(Loan, loan_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loan ID already exists")

    loan = Loan(
        id=loan_id,
        member_id=payload.member_id,
        amount=payload.amount,
        balance=payload.balance,
        rate=payload.rate,
        issued=payload.issued,
        due=payload.due,
        status=payload.status,
        type=payload.type,
    )
    db.add(loan)
    db.flush()
    _sync_member_loan_total(db, payload.member_id)
    db.commit()
    db.refresh(loan)
    write_audit_log(db, action="admin.loan_created", entity_type="loan", entity_id=loan.id, actor=admin, request=request, after=serialize_loan(loan))
    db.commit()
    return serialize_loan(loan)


@router.patch("/{loan_id}")
def update_loan(
    loan_id: str,
    payload: LoanUpdate,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    original_member_id = loan.member_id
    before = serialize_loan(loan)
    updates = payload.model_dump(exclude_unset=True, by_alias=False)

    if "member_id" in updates and updates["member_id"] is not None:
        if not db.get(Member, updates["member_id"]):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    for key, value in updates.items():
        if value is not None:
            setattr(loan, key, Decimal(str(value)) if key in {"amount", "balance", "rate"} else value)

    db.flush()
    _sync_member_loan_total(db, str(original_member_id))
    _sync_member_loan_total(db, str(loan.member_id))
    db.commit()
    db.refresh(loan)
    write_audit_log(db, action="admin.loan_updated", entity_type="loan", entity_id=loan.id, actor=admin, request=request, before=before, after=serialize_loan(loan))
    db.commit()
    return serialize_loan(loan)


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loan(loan_id: str, request: Request, admin=Depends(require_admin), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    member_id = loan.member_id
    before = serialize_loan(loan)
    db.delete(loan)
    db.flush()
    _sync_member_loan_total(db, str(member_id))
    write_audit_log(db, action="admin.loan_deleted", entity_type="loan", entity_id=loan_id, actor=admin, request=request, before=before)
    db.commit()

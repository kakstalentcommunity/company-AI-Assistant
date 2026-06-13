from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.access import ensure_member_access, is_admin, member_for_user
from app.database import get_db
from app.models.models import Loan, Member, Transaction, TransactionRequest
from app.notification_events import add_admin_notification, add_notification
from app.pagination import page_query, paginate, per_page_query
from app.schemas import TransactionCreate, TransactionRequestCreate, TransactionRequestReview, TransactionUpdate
from app.security import require_admin, require_user
from app.serializers import serialize_transaction, serialize_transaction_request
from app.services.fraud import sync_anomaly_flags

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _sync_member_loan_total(db: Session, member_id: str) -> None:
    member = db.get(Member, member_id)
    if not member:
        return
    loans = db.query(Loan).filter(Loan.member_id == member_id).all()
    member.loans = sum((loan.balance or Decimal("0") for loan in loans), Decimal("0"))


def _fmt_money(value) -> str:
    return f"KES {int(Decimal(str(value))):,}"


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _normalise_mpesa_receipt(value: str | None) -> str:
    return _clean_text(value).upper()


def _is_mpesa_channel(channel: str) -> bool:
    return channel.lower().replace("-", "").replace(" ", "") == "mpesa"


def _reference_exists(db: Session, ref: str) -> bool:
    return bool(db.query(Transaction).filter(Transaction.ref == ref).first() or db.query(TransactionRequest).filter(TransactionRequest.ref == ref).first())


def _is_unconfirmed_mpesa_stk_request(transaction_request: TransactionRequest) -> bool:
    return (
        _is_mpesa_channel(transaction_request.channel)
        and bool(transaction_request.mpesa_checkout_request_id)
        and not bool(transaction_request.mpesa_receipt_number)
    )


@router.get("")
def get_transactions(
    page: int | None = page_query(),
    per_page: int | None = per_page_query(),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Transaction)
        .options(joinedload(Transaction.member))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    )
    if not is_admin(user):
        member = member_for_user(db, user)
        query = query.filter(Transaction.member_id == member.id)

    if page is not None and per_page is not None:
        return paginate(query, page, per_page, serialize_transaction)

    return [serialize_transaction(transaction) for transaction in query.all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, request: Request, admin=Depends(require_admin), db: Session = Depends(get_db)):
    member = db.get(Member, payload.member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    transaction_id = payload.id or f"TXN-{db.query(Transaction).count() + 9001}"
    if db.get(Transaction, transaction_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction ID already exists")

    transaction = Transaction(
        id=transaction_id,
        member_id=payload.member_id,
        amount=payload.amount,
        type=payload.type,
        category=payload.category,
        date=payload.date,
        ref=payload.ref,
        channel=payload.channel,
        mpesa_receipt_number=_normalise_mpesa_receipt(payload.mpesa_receipt_number),
        mpesa_phone_number=_clean_text(payload.mpesa_phone_number),
        mpesa_checkout_request_id=_clean_text(payload.mpesa_checkout_request_id),
        mpesa_merchant_request_id=_clean_text(payload.mpesa_merchant_request_id),
        mpesa_result_code=_clean_text(payload.mpesa_result_code),
        mpesa_result_description=_clean_text(payload.mpesa_result_description),
    )
    db.add(transaction)
    db.commit()
    sync_anomaly_flags(db)
    db.refresh(transaction)
    write_audit_log(db, action="admin.transaction_created", entity_type="transaction", entity_id=transaction.id, actor=admin, request=request, after=serialize_transaction(transaction))
    db.commit()
    return serialize_transaction(transaction)


@router.get("/requests")
def list_transaction_requests(user=Depends(require_user), db: Session = Depends(get_db)):
    query = db.query(TransactionRequest).options(joinedload(TransactionRequest.member), joinedload(TransactionRequest.requester), joinedload(TransactionRequest.reviewer))
    if not is_admin(user):
        member = member_for_user(db, user)
        query = query.filter(TransactionRequest.member_id == member.id)
    else:
        query = query.order_by(TransactionRequest.status.asc(), TransactionRequest.created_at.desc())
    return [serialize_transaction_request(request) for request in query.all()]


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_transaction_request(payload: TransactionRequestCreate, request: Request, user=Depends(require_user), db: Session = Depends(get_db)):
    member = member_for_user(db, user)
    mpesa_receipt_number = _normalise_mpesa_receipt(payload.mpesa_receipt_number)
    if _is_mpesa_channel(payload.channel):
        mpesa_receipt_number = mpesa_receipt_number or _normalise_mpesa_receipt(payload.ref)

    duplicate_refs = [payload.ref]
    if mpesa_receipt_number and mpesa_receipt_number != payload.ref:
        duplicate_refs.append(mpesa_receipt_number)

    if any(_reference_exists(db, ref) for ref in duplicate_refs):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction reference already exists")

    if payload.loan_id:
        loan = db.get(Loan, payload.loan_id)
        if not loan or loan.member_id != member.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
        if loan.status == "Completed" or Decimal(str(loan.balance or 0)) <= 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loan is already fully repaid")
        if payload.type != "Credit":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Loan repayments must be credit transactions")
        if Decimal(str(payload.amount)) > Decimal(str(loan.balance or 0)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Repayment amount cannot exceed the loan balance")

    transaction_request = TransactionRequest(
        member_id=member.id,
        user_id=user.id,
        loan_id=payload.loan_id,
        amount=payload.amount,
        type=payload.type,
        category=payload.category,
        date=payload.date,
        ref=payload.ref,
        channel=payload.channel,
        mpesa_receipt_number=mpesa_receipt_number,
        mpesa_phone_number=_clean_text(payload.mpesa_phone_number),
        mpesa_checkout_request_id=_clean_text(payload.mpesa_checkout_request_id),
        mpesa_merchant_request_id=_clean_text(payload.mpesa_merchant_request_id),
        mpesa_result_code=_clean_text(payload.mpesa_result_code),
        mpesa_result_description=_clean_text(payload.mpesa_result_description),
        status="Pending",
    )
    db.add(transaction_request)
    db.commit()
    db.refresh(transaction_request)
    if transaction_request.loan_id:
        add_admin_notification(
            db,
            title="Loan repayment approval required",
            message=f"{member.name} submitted {_fmt_money(transaction_request.amount)} for loan {transaction_request.loan_id}. Ref: {transaction_request.ref}.",
            type="warning",
            entity_type="transaction_request",
            entity_id=str(transaction_request.id),
            created_by_user_id=user.id,
        )
    else:
        add_admin_notification(
            db,
            title="Transaction approval required",
            message=f"{member.name} requested a {transaction_request.type.lower()} of {_fmt_money(transaction_request.amount)}. Ref: {transaction_request.ref}.",
            type="warning",
            entity_type="transaction_request",
            entity_id=str(transaction_request.id),
            created_by_user_id=user.id,
        )
    write_audit_log(db, action="transaction.requested", entity_type="transaction_request", entity_id=str(transaction_request.id), actor=user, request=request, after=serialize_transaction_request(transaction_request))
    db.commit()
    return serialize_transaction_request(transaction_request)


@router.patch("/requests/{request_id}")
def review_transaction_request(
    request_id: int,
    payload: TransactionRequestReview,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    transaction_request = db.get(TransactionRequest, request_id)
    if not transaction_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction request not found")

    if transaction_request.status != "Pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction request has already been reviewed")

    if payload.status == "Approved" and _is_unconfirmed_mpesa_stk_request(transaction_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="M-Pesa payment has not been confirmed by Daraja yet",
        )

    transaction_request.status = payload.status
    transaction_request.reviewed_at = datetime.utcnow()
    transaction_request.reviewed_by_user_id = admin.id
    if payload.review_note is not None:
        transaction_request.review_note = payload.review_note

    if payload.status == "Approved":
        if db.query(Transaction).filter(Transaction.ref == transaction_request.ref).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction reference already exists")

        transaction_id = f"TXN-{db.query(Transaction).count() + 9001}"
        if db.get(Transaction, transaction_id):
            transaction_id = f"TXN-{int(db.query(Transaction).count()) + 9001}-{request_id}"

        transaction = Transaction(
            id=transaction_id,
            member_id=transaction_request.member_id,
            amount=transaction_request.amount,
            type=transaction_request.type,
            category=transaction_request.category,
            date=transaction_request.date,
            ref=transaction_request.ref,
            channel=transaction_request.channel,
            mpesa_receipt_number=transaction_request.mpesa_receipt_number or "",
            mpesa_phone_number=transaction_request.mpesa_phone_number or "",
            mpesa_checkout_request_id=transaction_request.mpesa_checkout_request_id or "",
            mpesa_merchant_request_id=transaction_request.mpesa_merchant_request_id or "",
            mpesa_result_code=transaction_request.mpesa_result_code or "",
            mpesa_result_description=transaction_request.mpesa_result_description or "",
            mpesa_raw_payload=transaction_request.mpesa_raw_payload,
        )
        db.add(transaction)

        member = db.get(Member, transaction_request.member_id)
        if transaction_request.loan_id:
            loan = db.get(Loan, transaction_request.loan_id)
            if not loan:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
            if loan.member_id != transaction_request.member_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loan does not belong to this member")

            repayment_amount = Decimal(str(transaction_request.amount))
            current_balance = Decimal(str(loan.balance or 0))
            if repayment_amount > current_balance:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Repayment amount cannot exceed the loan balance")

            loan.balance = current_balance - repayment_amount
            if loan.balance <= 0:
                loan.balance = Decimal("0")
                loan.status = "Completed"
            elif loan.status == "Completed":
                loan.status = "Active"
            _sync_member_loan_total(db, str(transaction_request.member_id))
        elif transaction_request.type == "Credit":
            member.savings += transaction_request.amount
        else:
            member.loans += transaction_request.amount

        db.commit()
        sync_anomaly_flags(db)
    else:
        db.commit()

    db.refresh(transaction_request)
    reviewed_label = transaction_request.status.lower()
    if transaction_request.loan_id:
        notification_title = f"Loan repayment {reviewed_label}"
        notification_message = (
            f"Your repayment of {_fmt_money(transaction_request.amount)} for loan {transaction_request.loan_id} was approved."
            if transaction_request.status == "Approved"
            else f"Your repayment of {_fmt_money(transaction_request.amount)} for loan {transaction_request.loan_id} was rejected{': ' + transaction_request.review_note if transaction_request.review_note else '.'}"
        )
    else:
        notification_title = f"Transaction request {reviewed_label}"
        notification_message = (
            f"Your {transaction_request.category} request for {_fmt_money(transaction_request.amount)} was approved."
            if transaction_request.status == "Approved"
            else f"Your {transaction_request.category} request for {_fmt_money(transaction_request.amount)} was rejected{': ' + transaction_request.review_note if transaction_request.review_note else '.'}"
        )
    add_notification(
        db,
        user_id=transaction_request.user_id,
        created_by_user_id=admin.id,
        title=notification_title,
        message=notification_message,
        type="success" if transaction_request.status == "Approved" else "danger",
        entity_type="transaction_request",
        entity_id=str(transaction_request.id),
    )
    write_audit_log(
        db,
        action=f"admin.transaction_request_{transaction_request.status.lower()}",
        entity_type="transaction_request",
        entity_id=str(transaction_request.id),
        actor=admin,
        request=request,
        after=serialize_transaction_request(transaction_request),
    )
    db.commit()
    return serialize_transaction_request(transaction_request)


@router.get("/{transaction_id}")
def get_transaction(transaction_id: str, user=Depends(require_user), db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    ensure_member_access(db, user, str(transaction.member_id))
    return serialize_transaction(transaction)


@router.patch("/{transaction_id}")
def update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    before = serialize_transaction(transaction)
    updates = payload.model_dump(exclude_unset=True, by_alias=False)

    if "member_id" in updates and updates["member_id"] is not None:
        if not db.get(Member, updates["member_id"]):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    for key, value in updates.items():
        if value is not None:
            setattr(transaction, key, value)

    db.commit()
    sync_anomaly_flags(db)
    db.refresh(transaction)
    write_audit_log(db, action="admin.transaction_updated", entity_type="transaction", entity_id=transaction.id, actor=admin, request=request, before=before, after=serialize_transaction(transaction))
    db.commit()
    return serialize_transaction(transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: str, request: Request, admin=Depends(require_admin), db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    before = serialize_transaction(transaction)
    db.delete(transaction)
    write_audit_log(db, action="admin.transaction_deleted", entity_type="transaction", entity_id=transaction_id, actor=admin, request=request, before=before)
    db.commit()
    sync_anomaly_flags(db)

import base64
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.access import member_for_user
from app.audit import write_audit_log
from app.config import (
    MPESA_BASE_URL,
    MPESA_BUSINESS_SHORTCODE,
    MPESA_CALLBACK_URL,
    MPESA_CONSUMER_KEY,
    MPESA_CONSUMER_SECRET,
    MPESA_PASSKEY,
    MPESA_REQUEST_TIMEOUT_SECONDS,
    MPESA_STK_TRANSACTION_TYPE,
)
from app.database import get_db
from app.models.models import Loan, Member, MpesaPayment, Transaction, TransactionRequest
from app.notification_events import add_admin_notification
from app.schemas import MpesaLoanRepaymentCreate, MpesaStkPushCreate
from app.security import require_user
from app.serializers import serialize_transaction_request

router = APIRouter(prefix="/api/mpesa", tags=["mpesa"])


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _receipt(value: Any) -> str:
    return _clean(value).upper()


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _normalise_phone(value: Any) -> str:
    digits = "".join(char for char in _clean(value) if char.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        return f"254{digits[1:]}"
    if digits.startswith("7") and len(digits) == 9:
        return f"254{digits}"
    return digits


def _raw_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"))


def _date_from_mpesa_time(value: str) -> str:
    digits = "".join(char for char in _clean(value) if char.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return date.today().isoformat()


def _fmt_money(value: Any) -> str:
    return f"KES {int(Decimal(str(value))):,}"


def _daraja_required_config() -> list[str]:
    required = {
        "MPESA_CONSUMER_KEY": MPESA_CONSUMER_KEY,
        "MPESA_CONSUMER_SECRET": MPESA_CONSUMER_SECRET,
        "MPESA_BUSINESS_SHORTCODE": MPESA_BUSINESS_SHORTCODE,
        "MPESA_PASSKEY": MPESA_PASSKEY,
        "MPESA_CALLBACK_URL": MPESA_CALLBACK_URL,
    }
    return [name for name, value in required.items() if not value]


def _ensure_daraja_configured() -> None:
    missing = _daraja_required_config()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Daraja STK Push is not configured. Missing: {', '.join(missing)}",
        )


def _daraja_password(timestamp: str) -> str:
    value = f"{MPESA_BUSINESS_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def _daraja_error(response: httpx.Response, fallback: str) -> HTTPException:
    detail = fallback
    try:
        payload = response.json()
        detail = (
            payload.get("errorMessage")
            or payload.get("ResponseDescription")
            or payload.get("CustomerMessage")
            or payload.get("errorCode")
            or fallback
        )
    except ValueError:
        if response.text:
            detail = response.text[:255]
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _request_daraja_access_token() -> str:
    _ensure_daraja_configured()
    try:
        response = httpx.get(
            f"{MPESA_BASE_URL}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET),
            timeout=MPESA_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach Daraja authentication API") from exc

    if response.status_code >= 400:
        raise _daraja_error(response, "Daraja authentication failed")

    try:
        token = _clean(response.json().get("access_token"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Daraja authentication returned an invalid response") from exc

    if not token:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Daraja authentication did not return an access token")
    return token


def _short_account_reference(value: str) -> str:
    cleaned = "".join(char for char in value.upper() if char.isalnum() or char in "-_")
    return (cleaned or "UMOJAFUNDS")[:12]


def _request_stk_push(*, phone_number: str, amount: Decimal, account_reference: str, description: str) -> dict[str, Any]:
    token = _request_daraja_access_token()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    payload = {
        "BusinessShortCode": MPESA_BUSINESS_SHORTCODE,
        "Password": _daraja_password(timestamp),
        "Timestamp": timestamp,
        "TransactionType": MPESA_STK_TRANSACTION_TYPE,
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": MPESA_BUSINESS_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": description[:100],
    }

    try:
        response = httpx.post(
            f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=MPESA_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach Daraja STK Push API") from exc

    if response.status_code >= 400:
        raise _daraja_error(response, "Daraja STK Push request failed")

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Daraja STK Push returned an invalid response") from exc

    if _clean(response_payload.get("ResponseCode")) != "0":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_clean(response_payload.get("ResponseDescription")) or "Daraja STK Push request was not accepted",
        )
    return response_payload


def _reference_exists(db: Session, ref: str) -> bool:
    if not ref:
        return False
    return bool(db.query(Transaction).filter(Transaction.ref == ref).first() or db.query(TransactionRequest).filter(TransactionRequest.ref == ref).first())


def _receipt_exists(db: Session, receipt: str) -> bool:
    if not receipt:
        return False
    return bool(
        db.query(Transaction).filter(Transaction.mpesa_receipt_number == receipt).first()
        or db.query(TransactionRequest).filter(TransactionRequest.mpesa_receipt_number == receipt).first()
    )


def _loan_repayment_category(loan: Loan) -> str:
    return f"Loan Repayment - {loan.type}"


def _create_pending_repayment_request(
    db: Session,
    *,
    member: Member,
    user_id: int,
    loan: Loan,
    amount: Decimal,
    payment_date: str,
    receipt_number: str,
    reference: str | None = None,
    phone_number: str = "",
    merchant_request_id: str = "",
    checkout_request_id: str = "",
    result_code: str = "",
    result_description: str = "",
    raw_payload_json: str | None = None,
) -> TransactionRequest:
    ref = _clean(reference) or receipt_number
    if not ref:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment reference is required")
    if _reference_exists(db, ref):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment reference already exists")
    if receipt_number and (_reference_exists(db, receipt_number) or _receipt_exists(db, receipt_number)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="M-Pesa receipt number already exists")

    if loan.status == "Completed" or Decimal(str(loan.balance or 0)) <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loan is already fully repaid")
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Repayment amount must be greater than zero")
    if amount > Decimal(str(loan.balance or 0)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Repayment amount cannot exceed the loan balance")

    transaction_request = TransactionRequest(
        member_id=member.id,
        user_id=user_id,
        loan_id=loan.id,
        amount=amount,
        type="Credit",
        category=_loan_repayment_category(loan),
        date=payment_date,
        ref=ref,
        channel="M-Pesa",
        mpesa_receipt_number=receipt_number,
        mpesa_phone_number=phone_number,
        mpesa_checkout_request_id=checkout_request_id,
        mpesa_merchant_request_id=merchant_request_id,
        mpesa_result_code=result_code,
        mpesa_result_description=result_description,
        mpesa_raw_payload=raw_payload_json,
        status="Pending",
    )
    db.add(transaction_request)
    db.flush()
    return transaction_request


def _create_pending_credit_request(
    db: Session,
    *,
    member: Member,
    user_id: int,
    amount: Decimal,
    payment_date: str,
    reference: str,
    category: str,
    phone_number: str = "",
    merchant_request_id: str = "",
    checkout_request_id: str = "",
    result_code: str = "",
    result_description: str = "",
    raw_payload_json: str | None = None,
) -> TransactionRequest:
    ref = _clean(reference)
    if not ref:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment reference is required")
    if _reference_exists(db, ref):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment reference already exists")
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment amount must be greater than zero")

    transaction_request = TransactionRequest(
        member_id=member.id,
        user_id=user_id,
        amount=amount,
        type="Credit",
        category=category.strip() or "Savings Deposit",
        date=payment_date,
        ref=ref,
        channel="M-Pesa",
        mpesa_phone_number=phone_number,
        mpesa_checkout_request_id=checkout_request_id,
        mpesa_merchant_request_id=merchant_request_id,
        mpesa_result_code=result_code,
        mpesa_result_description=result_description,
        mpesa_raw_payload=raw_payload_json,
        status="Pending",
    )
    db.add(transaction_request)
    db.flush()
    return transaction_request


def _record_mpesa_payment(
    db: Session,
    *,
    transaction_request: TransactionRequest | None,
    member_id: str | None,
    loan_id: str | None,
    amount: Decimal,
    receipt_number: str,
    phone_number: str,
    bill_ref_number: str = "",
    transaction_time: str = "",
    merchant_request_id: str = "",
    checkout_request_id: str = "",
    result_code: str = "",
    result_description: str = "",
    status_label: str,
    raw_payload_json: str,
) -> MpesaPayment:
    payment = None
    if checkout_request_id:
        payment = db.query(MpesaPayment).filter(MpesaPayment.checkout_request_id == checkout_request_id).first()
    if not payment and receipt_number:
        payment = db.query(MpesaPayment).filter(MpesaPayment.receipt_number == receipt_number).first()

    if not payment:
        payment = MpesaPayment(
            transaction_request_id=transaction_request.id if transaction_request else None,
            member_id=member_id,
            loan_id=loan_id,
            amount=amount,
            receipt_number=receipt_number,
            phone_number=phone_number,
            bill_ref_number=bill_ref_number,
            transaction_time=transaction_time,
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_description=result_description,
            status=status_label,
            raw_payload_json=raw_payload_json,
        )
        db.add(payment)
    else:
        payment.transaction_request_id = transaction_request.id if transaction_request else payment.transaction_request_id
        payment.member_id = member_id or payment.member_id
        payment.loan_id = loan_id or payment.loan_id
        payment.amount = amount if amount > 0 else payment.amount
        payment.receipt_number = receipt_number or payment.receipt_number
        payment.phone_number = phone_number or payment.phone_number
        payment.bill_ref_number = bill_ref_number or payment.bill_ref_number
        payment.transaction_time = transaction_time or payment.transaction_time
        payment.merchant_request_id = merchant_request_id or payment.merchant_request_id
        payment.checkout_request_id = checkout_request_id or payment.checkout_request_id
        payment.result_code = result_code or payment.result_code
        payment.result_description = result_description or payment.result_description
        payment.status = status_label
        payment.raw_payload_json = raw_payload_json
    db.flush()
    return payment


@router.post("/stk/push", status_code=status.HTTP_202_ACCEPTED)
def initiate_stk_push(
    payload: MpesaStkPushCreate,
    request: Request,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    member = member_for_user(db, user)
    amount = Decimal(str(payload.amount))
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment amount must be greater than zero")
    if amount != amount.to_integral_value():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="M-Pesa STK Push amount must be a whole KES amount")

    phone_number = _normalise_phone(payload.phone_number)
    if not phone_number.startswith("254") or len(phone_number) != 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Phone number must be a valid Kenyan Safaricom number such as 2547XXXXXXXX")

    loan: Loan | None = None
    payment_date = payload.date or date.today().isoformat()
    loan_id = None
    if payload.purpose == "loan_repayment":
        if not payload.loan_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Loan ID is required for loan repayment")
        loan = db.get(Loan, payload.loan_id)
        if not loan or loan.member_id != member.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
        if loan.status == "Completed" or Decimal(str(loan.balance or 0)) <= 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loan is already fully repaid")
        if amount > Decimal(str(loan.balance or 0)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Repayment amount cannot exceed the loan balance")
        loan_id = loan.id
        account_reference = _short_account_reference(loan.id)
        category = _loan_repayment_category(loan)
        description = f"Loan repayment {loan.id}"
    else:
        if payload.transaction_type != "Credit":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="M-Pesa STK Push can only collect credit payments")
        account_reference = _short_account_reference(f"SAV-{member.id}" if payload.purpose == "savings_deposit" else f"TX-{member.id}")
        category = (payload.category or ("Savings Deposit" if payload.purpose == "savings_deposit" else "Member Payment")).strip()
        description = category

    stk_response = _request_stk_push(
        phone_number=phone_number,
        amount=amount,
        account_reference=account_reference,
        description=description,
    )
    merchant_request_id = _clean(stk_response.get("MerchantRequestID"))
    checkout_request_id = _clean(stk_response.get("CheckoutRequestID"))
    response_code = _clean(stk_response.get("ResponseCode"))
    response_description = _clean(stk_response.get("ResponseDescription"))
    customer_message = _clean(stk_response.get("CustomerMessage"))
    if not checkout_request_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Daraja STK Push did not return a checkout request ID")

    raw_payload_json = _raw_payload(
        {
            "source": "stk_push_initiation",
            "purpose": payload.purpose,
            "memberId": member.id,
            "loanId": loan_id,
            "amount": str(amount),
            "phoneNumber": phone_number,
            "accountReference": account_reference,
            "darajaResponse": stk_response,
        }
    )

    if loan:
        transaction_request = _create_pending_repayment_request(
            db,
            member=member,
            user_id=user.id,
            loan=loan,
            amount=amount,
            payment_date=payment_date,
            receipt_number="",
            reference=checkout_request_id,
            phone_number=phone_number,
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            result_code=response_code,
            result_description=response_description or customer_message,
            raw_payload_json=raw_payload_json,
        )
        bill_ref_number = loan.id
    else:
        transaction_request = _create_pending_credit_request(
            db,
            member=member,
            user_id=user.id,
            amount=amount,
            payment_date=payment_date,
            reference=checkout_request_id,
            category=category,
            phone_number=phone_number,
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            result_code=response_code,
            result_description=response_description or customer_message,
            raw_payload_json=raw_payload_json,
        )
        bill_ref_number = account_reference

    payment = _record_mpesa_payment(
        db,
        transaction_request=transaction_request,
        member_id=member.id,
        loan_id=loan_id,
        amount=amount,
        receipt_number="",
        phone_number=phone_number,
        bill_ref_number=bill_ref_number,
        merchant_request_id=merchant_request_id,
        checkout_request_id=checkout_request_id,
        result_code=response_code,
        result_description=response_description or customer_message,
        status_label="AwaitingCustomer",
        raw_payload_json=raw_payload_json,
    )
    write_audit_log(
        db,
        action="mpesa.stk_push_initiated",
        entity_type="mpesa_payment",
        entity_id=str(payment.id),
        actor=user,
        request=request,
        after={
            "transactionRequestId": transaction_request.id,
            "checkoutRequestId": checkout_request_id,
            "purpose": payload.purpose,
            "amount": str(amount),
        },
    )
    db.commit()
    db.refresh(transaction_request)
    return {
        "transactionRequest": serialize_transaction_request(transaction_request),
        "merchantRequestId": merchant_request_id,
        "checkoutRequestId": checkout_request_id,
        "responseCode": response_code,
        "responseDescription": response_description,
        "customerMessage": customer_message,
    }


@router.post("/loan-repayments", status_code=status.HTTP_201_CREATED)
def create_mpesa_loan_repayment(
    payload: MpesaLoanRepaymentCreate,
    request: Request,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    member = member_for_user(db, user)
    loan = db.get(Loan, payload.loan_id)
    if not loan or loan.member_id != member.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    receipt_number = _receipt(payload.mpesa_receipt_number)
    if not receipt_number:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="M-Pesa receipt number is required")

    amount = Decimal(str(payload.amount))
    payment_date = payload.date or date.today().isoformat()
    raw_payload_json = _raw_payload({
        "source": "member_submission",
        "loanId": loan.id,
        "amount": str(amount),
        "phoneNumber": _normalise_phone(payload.phone_number),
        "mpesaReceiptNumber": receipt_number,
        "date": payment_date,
    })
    transaction_request = _create_pending_repayment_request(
        db,
        member=member,
        user_id=user.id,
        loan=loan,
        amount=amount,
        payment_date=payment_date,
        receipt_number=receipt_number,
        phone_number=_normalise_phone(payload.phone_number),
        result_code="Manual",
        result_description="M-Pesa receipt submitted by member",
        raw_payload_json=raw_payload_json,
    )
    payment = _record_mpesa_payment(
        db,
        transaction_request=transaction_request,
        member_id=member.id,
        loan_id=loan.id,
        amount=amount,
        receipt_number=receipt_number,
        phone_number=_normalise_phone(payload.phone_number),
        bill_ref_number=loan.id,
        transaction_time=payment_date,
        result_code="Manual",
        result_description="M-Pesa receipt submitted by member",
        status_label="PendingReview",
        raw_payload_json=raw_payload_json,
    )
    add_admin_notification(
        db,
        title="M-Pesa loan repayment approval required",
        message=f"{member.name} submitted {_fmt_money(amount)} for loan {loan.id}. M-Pesa ref: {receipt_number}.",
        type="warning",
        entity_type="transaction_request",
        entity_id=str(transaction_request.id),
        created_by_user_id=user.id,
    )
    write_audit_log(
        db,
        action="mpesa.loan_repayment_recorded",
        entity_type="mpesa_payment",
        entity_id=str(payment.id),
        actor=user,
        request=request,
        after=serialize_transaction_request(transaction_request),
    )
    db.commit()
    db.refresh(transaction_request)
    return serialize_transaction_request(transaction_request)


@router.post("/c2b/confirmation")
def receive_c2b_confirmation(
    request: Request,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    receipt_number = _receipt(payload.get("TransID"))
    bill_ref_number = _clean(payload.get("BillRefNumber"))
    amount = _decimal(payload.get("TransAmount"))
    phone_number = _normalise_phone(payload.get("MSISDN"))
    transaction_time = _clean(payload.get("TransTime"))
    raw_payload_json = _raw_payload(payload)
    transaction_request: TransactionRequest | None = None
    status_label = "Unmatched"
    loan = db.get(Loan, bill_ref_number) if bill_ref_number else None
    member = db.get(Member, loan.member_id) if loan else None

    if receipt_number and loan and member and member.user_id and not _reference_exists(db, receipt_number) and not _receipt_exists(db, receipt_number):
        try:
            transaction_request = _create_pending_repayment_request(
                db,
                member=member,
                user_id=int(member.user_id),
                loan=loan,
                amount=amount,
                payment_date=_date_from_mpesa_time(transaction_time),
                receipt_number=receipt_number,
                phone_number=phone_number,
                raw_payload_json=raw_payload_json,
                result_code="0",
                result_description="M-Pesa C2B payment received",
            )
            status_label = "PendingReview"
            add_admin_notification(
                db,
                title="M-Pesa loan repayment approval required",
                message=f"M-Pesa received {_fmt_money(amount)} for loan {loan.id}. Ref: {receipt_number}.",
                type="warning",
                entity_type="transaction_request",
                entity_id=str(transaction_request.id),
            )
        except HTTPException:
            status_label = "Unmatched"
    elif receipt_number and (_reference_exists(db, receipt_number) or _receipt_exists(db, receipt_number)):
        status_label = "Duplicate"

    payment = _record_mpesa_payment(
        db,
        transaction_request=transaction_request,
        member_id=member.id if member else None,
        loan_id=loan.id if loan else None,
        amount=amount,
        receipt_number=receipt_number,
        phone_number=phone_number,
        bill_ref_number=bill_ref_number,
        transaction_time=transaction_time,
        result_code="0" if status_label == "PendingReview" else "",
        result_description="M-Pesa C2B payment received" if status_label == "PendingReview" else "Could not match payment to a member loan",
        status_label=status_label,
        raw_payload_json=raw_payload_json,
    )
    write_audit_log(
        db,
        action="mpesa.c2b_confirmation_received",
        entity_type="mpesa_payment",
        entity_id=str(payment.id),
        request=request,
        after={
            "status": status_label,
            "receiptNumber": receipt_number,
            "billRefNumber": bill_ref_number,
            "transactionRequestId": transaction_request.id if transaction_request else None,
        },
    )
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/stk/callback")
def receive_stk_callback(
    request: Request,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    callback = payload.get("Body", {}).get("stkCallback", {}) if isinstance(payload.get("Body"), dict) else {}
    merchant_request_id = _clean(callback.get("MerchantRequestID"))
    checkout_request_id = _clean(callback.get("CheckoutRequestID"))
    result_code = _clean(callback.get("ResultCode"))
    result_description = _clean(callback.get("ResultDesc"))
    metadata_items = callback.get("CallbackMetadata", {}).get("Item", []) if isinstance(callback.get("CallbackMetadata"), dict) else []
    metadata = {item.get("Name"): item.get("Value") for item in metadata_items if isinstance(item, dict)}
    receipt_number = _receipt(metadata.get("MpesaReceiptNumber"))
    amount = _decimal(metadata.get("Amount"))
    phone_number = _normalise_phone(metadata.get("PhoneNumber"))
    transaction_time = _clean(metadata.get("TransactionDate"))
    raw_payload_json = _raw_payload(payload)

    query = db.query(TransactionRequest).filter(TransactionRequest.status == "Pending")
    transaction_request = None
    if checkout_request_id:
        transaction_request = query.filter(TransactionRequest.mpesa_checkout_request_id == checkout_request_id).first()
    if not transaction_request and merchant_request_id:
        transaction_request = query.filter(TransactionRequest.mpesa_merchant_request_id == merchant_request_id).first()

    status_label = "Received"
    loan_id = None
    member_id = None
    callback_success = result_code == "0"
    was_waiting_for_receipt = False
    if transaction_request:
        was_waiting_for_receipt = not bool(transaction_request.mpesa_receipt_number)
        status_label = "PendingReview" if callback_success else "Failed"
        loan_id = transaction_request.loan_id
        member_id = transaction_request.member_id
        if receipt_number and transaction_request.ref != receipt_number and not _reference_exists(db, receipt_number):
            transaction_request.ref = receipt_number
        transaction_request.mpesa_receipt_number = receipt_number or transaction_request.mpesa_receipt_number
        transaction_request.mpesa_phone_number = phone_number or transaction_request.mpesa_phone_number
        transaction_request.mpesa_checkout_request_id = checkout_request_id or transaction_request.mpesa_checkout_request_id
        transaction_request.mpesa_merchant_request_id = merchant_request_id or transaction_request.mpesa_merchant_request_id
        transaction_request.mpesa_result_code = result_code
        transaction_request.mpesa_result_description = result_description
        transaction_request.mpesa_raw_payload = raw_payload_json
        if not callback_success and transaction_request.status == "Pending":
            transaction_request.status = "Rejected"
            transaction_request.reviewed_at = datetime.utcnow()
            transaction_request.review_note = result_description or "M-Pesa payment was not completed"

    payment = _record_mpesa_payment(
        db,
        transaction_request=transaction_request,
        member_id=member_id,
        loan_id=loan_id,
        amount=amount,
        receipt_number=receipt_number,
        phone_number=phone_number,
        transaction_time=transaction_time,
        merchant_request_id=merchant_request_id,
        checkout_request_id=checkout_request_id,
        result_code=result_code,
        result_description=result_description,
        status_label=status_label,
        raw_payload_json=raw_payload_json,
    )
    if transaction_request and callback_success and was_waiting_for_receipt:
        member = db.get(Member, transaction_request.member_id)
        notification_amount = amount if amount > 0 else Decimal(str(transaction_request.amount or 0))
        if transaction_request.loan_id:
            title = "M-Pesa loan repayment approval required"
            message = f"{member.name if member else transaction_request.member_id} paid {_fmt_money(notification_amount)} for loan {transaction_request.loan_id}. Ref: {receipt_number or checkout_request_id}."
        else:
            title = "M-Pesa transaction approval required"
            message = f"{member.name if member else transaction_request.member_id} paid {_fmt_money(notification_amount)} for {transaction_request.category}. Ref: {receipt_number or checkout_request_id}."
        add_admin_notification(
            db,
            title=title,
            message=message,
            type="warning",
            entity_type="transaction_request",
            entity_id=str(transaction_request.id),
            created_by_user_id=transaction_request.user_id,
        )
    write_audit_log(
        db,
        action="mpesa.stk_callback_received",
        entity_type="mpesa_payment",
        entity_id=str(payment.id),
        request=request,
        after={
            "status": status_label,
            "receiptNumber": receipt_number,
            "checkoutRequestId": checkout_request_id,
            "transactionRequestId": transaction_request.id if transaction_request else None,
        },
    )
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}

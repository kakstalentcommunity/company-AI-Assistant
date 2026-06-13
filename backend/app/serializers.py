import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

from app.models.models import (
    AnomalyFlag,
    AuditLog,
    Loan,
    LoanApplication,
    Member,
    MemberProfile,
    MembershipApplication,
    Notification,
    PortfolioSnapshot,
    ProductAnalyticsAlert,
    ProductAnalyticsInsight,
    ProductAnalyticsEvent,
    Transaction,
    TransactionRequest,
)
from app.models.security import SecurityEvent


def _money(value) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _rate(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _json_list(value: str):
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def serialize_member(member: Member) -> dict:
    return {
        "id": member.id,
        "userId": member.user_id,
        "name": member.name,
        "email": member.email,
        "savings": _money(member.savings),
        "loans": _money(member.loans),
        "status": member.status,
        "joined": member.joined,
        "shares": member.shares,
    }


def serialize_loan(loan: Loan) -> dict:
    return {
        "id": loan.id,
        "member": loan.member.name if loan.member else loan.member_id,
        "amount": _money(loan.amount),
        "balance": _money(loan.balance),
        "rate": _rate(loan.rate),
        "issued": loan.issued,
        "due": loan.due,
        "status": loan.status,
        "type": loan.type,
    }


def serialize_transaction(transaction: Transaction) -> dict:
    return {
        "id": transaction.id,
        "member": transaction.member.name if transaction.member else transaction.member_id,
        "amount": _money(transaction.amount),
        "type": transaction.type,
        "category": transaction.category,
        "date": transaction.date,
        "ref": transaction.ref,
        "channel": transaction.channel,
        "mpesaReceiptNumber": transaction.mpesa_receipt_number or None,
        "mpesaPhoneNumber": transaction.mpesa_phone_number or None,
        "mpesaCheckoutRequestId": transaction.mpesa_checkout_request_id or None,
        "mpesaMerchantRequestId": transaction.mpesa_merchant_request_id or None,
        "mpesaResultCode": transaction.mpesa_result_code or None,
        "mpesaResultDescription": transaction.mpesa_result_description or None,
    }


def serialize_transaction_request(request: TransactionRequest) -> dict:
    return {
        "id": request.id,
        "member": request.member.name if request.member else request.member_id,
        "loanId": request.loan_id,
        "requester": request.requester.name if request.requester else None,
        "amount": _money(request.amount),
        "type": request.type,
        "category": request.category,
        "date": request.date,
        "ref": request.ref,
        "channel": request.channel,
        "mpesaReceiptNumber": request.mpesa_receipt_number or None,
        "mpesaPhoneNumber": request.mpesa_phone_number or None,
        "mpesaCheckoutRequestId": request.mpesa_checkout_request_id or None,
        "mpesaMerchantRequestId": request.mpesa_merchant_request_id or None,
        "mpesaResultCode": request.mpesa_result_code or None,
        "mpesaResultDescription": request.mpesa_result_description or None,
        "status": request.status,
        "reviewNote": request.review_note or "",
        "reviewedAt": request.reviewed_at.isoformat() if request.reviewed_at else None,
        "reviewedBy": request.reviewer.name if request.reviewer else None,
        "createdAt": request.created_at.isoformat(),
    }


def serialize_portfolio_snapshot(snapshot: PortfolioSnapshot) -> dict:
    return {
        "month": snapshot.month,
        "savings": _money(snapshot.savings),
        "loans": _money(snapshot.loans),
        "repayments": _money(snapshot.repayments),
    }


def _parse_record_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _next_month(value: date) -> date:
    return date(value.year + (1 if value.month == 12 else 0), 1 if value.month == 12 else value.month + 1, 1)


def _shift_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _is_savings_transaction(transaction: Transaction) -> bool:
    text = f"{transaction.category} {transaction.channel}".lower()
    return not any(keyword in text for keyword in ("loan", "repayment", "fee", "charge", "interest"))


def _is_repayment_transaction(transaction: Transaction) -> bool:
    text = f"{transaction.category} {transaction.channel}".lower()
    return "repay" in text or "loan payment" in text or "installment" in text


def build_portfolio_growth(
    members: Iterable[Member],
    loans: Iterable[Loan],
    transactions: Iterable[Transaction],
    months: int = 7,
) -> list[dict]:
    """Derive chartable portfolio rows from live records when snapshots are absent."""
    members = list(members)
    loans = list(loans)
    transactions = list(transactions)

    if not members and not loans and not transactions:
        return []

    dated_values = [
        parsed
        for parsed in (
            [_parse_record_date(loan.issued) for loan in loans]
            + [_parse_record_date(transaction.date) for transaction in transactions]
        )
        if parsed is not None
    ]
    latest_month = _month_start(max(dated_values) if dated_values else datetime.utcnow().date())
    first_month = _shift_months(latest_month, -(months - 1))
    month_starts = [_shift_months(first_month, offset) for offset in range(months)]

    current_savings = sum(_money(member.savings) for member in members)
    current_loan_balance = sum(_money(loan.balance) for loan in loans)

    savings_activity: dict[date, int] = {month: 0 for month in month_starts}
    repayment_activity: dict[date, int] = {month: 0 for month in month_starts}
    loan_balances_by_issued_month: dict[date, int] = {month: 0 for month in month_starts}

    for transaction in transactions:
        transaction_date = _parse_record_date(transaction.date)
        if transaction_date is None:
            continue
        month = _month_start(transaction_date)
        amount = _money(transaction.amount)
        if _is_savings_transaction(transaction):
            savings_activity[month] = savings_activity.get(month, 0) + (amount if transaction.type == "Credit" else -amount)
        if _is_repayment_transaction(transaction):
            repayment_activity[month] = repayment_activity.get(month, 0) + amount

    for loan in loans:
        issued_date = _parse_record_date(loan.issued)
        if issued_date is None:
            continue
        month = _month_start(issued_date)
        loan_balances_by_issued_month[month] = loan_balances_by_issued_month.get(month, 0) + _money(loan.balance)

    rows: list[dict] = []
    for month in month_starts:
        next_month = _next_month(month)
        savings_after_month = sum(
            amount
            for activity_month, amount in savings_activity.items()
            if activity_month >= next_month
        )
        loan_balance_after_month = sum(
            amount
            for issued_month, amount in loan_balances_by_issued_month.items()
            if issued_month >= next_month
        )
        rows.append({
            "month": month.strftime("%b"),
            "savings": max(current_savings - savings_after_month, 0),
            "loans": max(current_loan_balance - loan_balance_after_month, 0),
            "repayments": repayment_activity.get(month, 0),
        })

    return rows


def serialize_member_profile(profile: MemberProfile) -> dict:
    return {
        "employer": profile.employer,
        "employerType": profile.employer_type,
        "estimatedMonthlyIncome": _money(profile.estimated_monthly_income),
        "mpesaMonthlyInflows": [_money(value) for value in _json_list(profile.mpesa_monthly_inflows)],
        "guarantors": _json_list(profile.guarantors),
        "monthlyExpenses": _money(profile.monthly_expenses),
        "completedLoans": profile.completed_loans,
        "defaultedLoans": profile.defaulted_loans,
    }


def serialize_anomaly_flags(flags: Iterable[AnomalyFlag]) -> dict:
    return {
        flag.transaction_id: {
            "level": flag.level,
            "reason": flag.reason,
        }
        for flag in flags
    }


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "userId": notification.user_id,
        "recipient": notification.user.name if notification.user else "All admins",
        "createdByUserId": notification.created_by_user_id,
        "createdBy": notification.created_by.name if notification.created_by else None,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "entityType": notification.entity_type,
        "entityId": notification.entity_id,
        "readAt": notification.read_at.isoformat() if notification.read_at else None,
        "createdAt": notification.created_at.isoformat(),
    }


def build_loan_distribution(loans: Iterable[Loan]) -> list[dict]:
    colors = ["#0F4C35", "#C8A84B", "#2E7D56", "#1A6647", "#E07B39", "#475569"]
    counts: dict[str, int] = {}
    loans = list(loans)

    for loan in loans:
        counts[loan.type] = counts.get(loan.type, 0) + 1

    total = len(loans) or 1
    return [
        {
            "name": name,
            "value": round((count / total) * 100),
            "color": colors[index % len(colors)],
        }
        for index, (name, count) in enumerate(counts.items())
    ]


def serialize_membership_application(application: MembershipApplication) -> dict:
    return {
        "id": application.id,
        "userId": application.user_id,
        "memberId": application.member_id,
        "name": application.name,
        "email": application.email,
        "phone": application.phone,
        "nationalId": application.national_id,
        "address": application.address,
        "status": application.status,
        "notes": application.notes,
        "createdAt": application.created_at.isoformat(),
        "reviewedAt": application.reviewed_at.isoformat() if application.reviewed_at else None,
    }


def serialize_loan_application(application: LoanApplication) -> dict:
    return {
        "id": application.id,
        "userId": application.user_id,
        "memberId": application.member_id,
        "member": application.member.name if application.member else application.member_id,
        "loanId": application.loan_id,
        "amount": _money(application.amount),
        "type": application.type,
        "purpose": application.purpose,
        "termMonths": application.term_months,
        "status": application.status,
        "notes": application.notes,
        "createdAt": application.created_at.isoformat(),
        "reviewedAt": application.reviewed_at.isoformat() if application.reviewed_at else None,
    }


def serialize_product_analytics_event(event: ProductAnalyticsEvent) -> dict:
    return {
        "id": event.id,
        "userId": event.user_id,
        "sessionId": event.session_id,
        "eventName": event.event_name,
        "feature": event.feature,
        "funnelName": event.funnel_name,
        "funnelStep": event.funnel_step,
        "device": event.device,
        "path": event.path,
        "durationSeconds": event.duration_seconds,
        "properties": json.loads(event.properties_json or "{}"),
        "occurredAt": event.occurred_at.isoformat(),
    }


def serialize_product_alert(alert: ProductAnalyticsAlert) -> dict:
    return {
        "id": alert.id,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "metric": alert.metric,
        "currentValue": float(alert.current_value),
        "thresholdValue": float(alert.threshold_value),
        "status": alert.status,
        "detectedAt": alert.detected_at.isoformat(),
    }


def serialize_product_insight(insight: ProductAnalyticsInsight) -> dict:
    return {
        "id": insight.id,
        "category": insight.category,
        "title": insight.title,
        "narrative": insight.narrative,
        "recommendation": insight.recommendation,
        "confidence": insight.confidence,
        "generatedAt": insight.generated_at.isoformat(),
    }


def serialize_audit_log(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "actorUserId": log.actor_user_id,
        "action": log.action,
        "entityType": log.entity_type,
        "entityId": log.entity_id,
        "ipAddress": log.ip_address,
        "userAgent": log.user_agent,
        "before": json.loads(log.before_json or "{}"),
        "after": json.loads(log.after_json or "{}"),
        "createdAt": log.created_at.isoformat(),
    }


def serialize_security_event(event: SecurityEvent) -> dict:
    try:
        details = json.loads(event.details or "{}")
    except json.JSONDecodeError:
        details = {"message": event.details or ""}

    return {
        "id": event.id,
        "eventType": event.event_type,
        "severity": event.severity,
        "userId": event.user_id,
        "ipAddress": event.ip_address,
        "userAgent": event.user_agent,
        "method": event.method,
        "path": event.path,
        "statusCode": event.status_code,
        "details": details,
        "createdAt": event.created_at.isoformat(),
    }

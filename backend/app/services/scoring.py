import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import AnomalyFlag, Loan, LoanScoreEvent, Member, MemberProfile, Transaction

MODEL_VERSION = "rules-3.0"
LOAN_TYPE_RISK = {
    "Emergency": 1.10,
    "Business": 1.00,
    "Agricultural": 0.96,
    "Development": 0.92,
    "Education": 0.88,
}


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0, high: float = 100) -> int:
    return int(round(max(low, min(high, value))))


def _json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _months_since(date_text: str) -> float:
    try:
        joined = datetime.fromisoformat(date_text[:10])
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - joined).days / 30)


def _parse_date(date_text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(date_text)[:10])
    except ValueError:
        return None


def _trend(current: int, previous: int | None) -> str:
    if previous is None:
        return "flat"
    if current >= previous + 4:
        return "up"
    if current <= previous - 4:
        return "down"
    return "flat"


def _risk_band(score: int) -> str:
    if score >= 80:
        return "Very Low"
    if score >= 66:
        return "Low"
    if score >= 51:
        return "Medium"
    if score >= 36:
        return "High"
    return "Very High"


def _recommendation(score: int) -> str:
    if score >= 72:
        return "Approve"
    if score >= 57:
        return "Approve with Conditions"
    if score >= 40:
        return "Counter-offer"
    return "Decline"


def _previous_dimensions(event: LoanScoreEvent | None) -> dict[str, int]:
    if not event:
        return {}
    try:
        dimensions = json.loads(event.dimensions_json)
    except json.JSONDecodeError:
        return {}
    return {
        str(item.get("name")): int(item.get("score", 0))
        for item in dimensions
        if isinstance(item, dict) and item.get("name")
    }


def _history_adjustment(history: list[LoanScoreEvent]) -> int:
    if len(history) < 2:
        return 0

    recent = list(reversed(history[:5]))
    deltas = [
        recent[index].composite - recent[index - 1].composite
        for index in range(1, len(recent))
    ]
    avg_delta = mean(deltas) if deltas else 0
    return _clamp(avg_delta * 0.8, -5, 5)


def _recent_transactions(db: Session, member_id: str) -> list[Transaction]:
    since = (datetime.utcnow() - timedelta(days=210)).date().isoformat()
    return (
        db.query(Transaction)
        .filter(Transaction.member_id == member_id, Transaction.date >= since)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(250)
        .all()
    )

###This function extracts financial transaction features for a specific member from a database, 
##grouping them by month and calculating various statistical metrics.
def _transaction_features(db: Session, member_id: str) -> dict:
    rows = _recent_transactions(db, member_id)
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"credit": 0.0, "debit": 0.0})
    channels: set[str] = set()

    for row in rows:
        month = str(row.date)[:7]
        amount = _number(row.amount)
        row_type = str(row.type)
        if row_type == "Credit":
            monthly[month]["credit"] += amount
        else:
            monthly[month]["debit"] += amount
        if row.channel:
            channels.add(str(row.channel))

    ordered_months = sorted(monthly)
    credits = [monthly[month]["credit"] for month in ordered_months]
    debits = [monthly[month]["debit"] for month in ordered_months]
    net_flows = [credit - debit for credit, debit in zip(credits, debits)]
    avg_credit = mean(credits) if credits else 0.0
    avg_debit = mean(debits) if debits else 0.0
    avg_net = mean(net_flows) if net_flows else 0.0
    negative_months = sum(1 for value in net_flows if value < 0)
    credit_cv = (
        math.sqrt(mean([(value - avg_credit) ** 2 for value in credits])) / max(avg_credit, 1)
        if credits
        else 0.0
    )
    trend = 0.0
    if len(credits) >= 4:
        recent_avg = mean(credits[-3:])
        previous_avg = mean(credits[: max(1, len(credits) - 3)])
        trend = (recent_avg - previous_avg) / max(previous_avg, 1)

    flagged_count = (
        db.query(AnomalyFlag)
        .join(Transaction, AnomalyFlag.transaction_id == Transaction.id)
        .filter(Transaction.member_id == member_id)
        .count()
    )

    return {
        "transaction_count": len(rows),
        "month_count": len(monthly),
        "avg_credit": avg_credit,
        "avg_debit": avg_debit,
        "avg_net": avg_net,
        "negative_months": negative_months,
        "credit_cv": credit_cv,
        "credit_trend": trend,
        "flagged_count": flagged_count,
        "channel_count": len(channels),
    }


def calculate_score(data: dict) -> int:
    score = 0

    if _number(data.get("salary")) > 100000:
        score += 20
    if _number(data.get("savings")) > 50000:
        score += 20
    if int(_number(data.get("defaults"))) == 0:
        score += 25
    if int(_number(data.get("active_loans"))) < 2:
        score += 15
    if _number(data.get("monthly_inflow")) > 80000:
        score += 10
    if data.get("has_guarantor", False):
        score += 10

    return _clamp(score)


def score_member_loan(
    db: Session,
    member_id: str,
    loan_amount: float,
    loan_type: str,
    persist: bool = True,
) -> dict:
    if loan_amount <= 0:
        raise ValueError("loanAmount must be greater than zero")

    member = db.get(Member, member_id)
    if not member:
        raise ValueError("Member not found")

    profile = db.get(MemberProfile, member_id)
    if not profile:
        raise ValueError("Member profile data is required before scoring a loan")

    active_loans = (
        db.query(Loan)
        .filter(Loan.member_id == member_id, Loan.status != "Completed")
        .all()
    )
    overdue_count = sum(1 for loan in active_loans if loan.status == "Overdue")
    active_balance = sum(_number(loan.balance) for loan in active_loans)
    active_principal = sum(_number(loan.amount) for loan in active_loans)
    exposure_ratio = active_balance / max(_number(member.savings), 1)

    history = (
        db.query(LoanScoreEvent)
        .filter(LoanScoreEvent.member_id == member_id)
        .order_by(LoanScoreEvent.created_at.desc(), LoanScoreEvent.id.desc())
        .limit(6)
        .all()
    )
    previous = history[0] if history else None
    previous_dims = _previous_dimensions(previous)

    inflows = [_number(value) for value in _json_list(profile.mpesa_monthly_inflows)]
    if not inflows:
        inflows = [_number(profile.estimated_monthly_income)]

    avg_inflow = mean(inflows)
    variance = mean([(value - avg_inflow) ** 2 for value in inflows]) if avg_inflow else 0
    cv = math.sqrt(variance) / max(avg_inflow, 1)
    tenure_months = _months_since(member.joined)

    income = _number(profile.estimated_monthly_income)
    expenses = _number(profile.monthly_expenses)
    disposable = max(0, income - expenses)
    requested_amount = _number(loan_amount)
    tx = _transaction_features(db, member_id)
    observed_inflow = tx["avg_credit"] or avg_inflow
    income_evidence = max(avg_inflow, observed_inflow)
    loan_type_risk = LOAN_TYPE_RISK.get(loan_type, 1.0)

    income_score = min(82, (income_evidence / max(income, 1)) * 76)
    consistency_penalty = min(34, max(cv, tx["credit_cv"]) * 70)
    trend_bonus = max(-10, min(10, tx["credit_trend"] * 35))
    salary_pattern = _clamp(income_score - consistency_penalty + trend_bonus + 18, 10)

    expected_savings = tenure_months * income_evidence * 0.15
    savings_ratio = _number(member.savings) / max(expected_savings, 1)
    savings_buffer_months = _number(member.savings) / max(expenses, 1)
    savings_consistency = _clamp(savings_ratio * 58 + min(30, savings_buffer_months * 5) - min(18, exposure_ratio * 4))

    status = member.status or "Active"
    base_repayment = 10 if overdue_count else 22 if status == "Suspended" else 50 if status == "Inactive" else 68
    completed_bonus = min(28, profile.completed_loans * 14)
    default_penalty = profile.defaulted_loans * 30
    exposure_penalty = min(18, active_balance / max(income * 6, 1) * 12)
    repayment_history = _clamp(base_repayment + completed_bonus - default_penalty - exposure_penalty, 5)

    net_flow_bonus = max(-15, min(15, tx["avg_net"] / max(income, 1) * 18))
    activity_bonus = min(14, tx["month_count"] * 2 + tx["channel_count"])
    anomaly_penalty = min(30, tx["flagged_count"] * 10)
    mpesa_inflow = _clamp((observed_inflow / 150000) * 48 + activity_bonus + net_flow_bonus - anomaly_penalty + (10 if cv < 0.1 else 0))

    employer_base = {
        "Government": 94,
        "Formal": 80,
        "Self-Employed": 58,
        "Informal": 36,
    }.get(profile.employer_type, 50)
    employer_stability = _clamp(employer_base + min(12, tenure_months / 5))

    guarantors = _json_list(profile.guarantors)
    guarantor_strength = 28 if len(guarantors) == 0 else 64 if len(guarantors) == 1 else 88

    estimated_installment = ((requested_amount * loan_type_risk) / 18) if requested_amount else 0
    dscr = estimated_installment / max(disposable, 1)
    total_installment_pressure = (estimated_installment + (active_balance / 18)) / max(disposable, 1)
    spending_behavior = _clamp(
        (disposable / max(income, 1)) * 70
        - total_installment_pressure * 32
        - tx["negative_months"] * 4
        + 18,
        5,
    )

    data_points = tx["transaction_count"] + len(inflows) + len(active_loans) + profile.completed_loans
    data_confidence = _clamp(min(100, data_points * 3 + tx["month_count"] * 8 + (20 if profile else 0)))

    raw_dimensions = [
        ("Salary Pattern", salary_pattern, 0.20, f"KES {round(income_evidence / 1000)}K avg/mo; CV {(max(cv, tx['credit_cv']) * 100):.0f}%; trend {tx['credit_trend'] * 100:.0f}%"),
        ("Savings Consistency", savings_consistency, 0.17, f"{round(min(savings_ratio, 9.9) * 100)}% expected savings; {savings_buffer_months:.1f} expense-month buffer"),
        ("Repayment History", repayment_history, 0.22, f"{profile.completed_loans} completed; {overdue_count} overdue; {profile.defaulted_loans} defaulted; KES {round(active_balance / 1000)}K active"),
        ("Mobile Money Inflow", mpesa_inflow, 0.15, f"KES {round(observed_inflow / 1000)}K observed/mo; {tx['transaction_count']} tx; {tx['flagged_count']} anomaly flag(s)"),
        ("Employer Stability", employer_stability, 0.12, f"{profile.employer_type}; {profile.employer}"),
        ("Guarantor Strength", guarantor_strength, 0.07, f"{len(guarantors)} guarantor(s) registered"),
        ("Spending Behavior", spending_behavior, 0.07, f"{round((disposable / max(income, 1)) * 100)}% disposable; DSCR {dscr:.1f}x; {tx['negative_months']} negative month(s)"),
    ]

    dimensions = [
        {
            "name": name,
            "score": score,
            "weight": weight,
            "signal": signal,
            "trend": _trend(score, previous_dims.get(name)),
        }
        for name, score, weight, signal in raw_dimensions
    ]

    rule_composite = round(sum(item["score"] * item["weight"] for item in dimensions))
    trend_adjustment = _history_adjustment(history)
    confidence_adjustment = -4 if data_confidence < 45 else -2 if data_confidence < 65 else 0
    composite = _clamp(rule_composite + trend_adjustment + confidence_adjustment)
    repayment_likelihood = _clamp(composite * 0.91 + 7, 0, 98)
    affordability_ratio = requested_amount / max(income, 1)
    delinquency_risk_90d = _clamp((100 - composite) * 0.50 + max(0, dscr - 0.55) * 18 + tx["flagged_count"] * 4, 2, 98)
    default_risk = _risk_band(composite)
    recommendation = _recommendation(composite)

    monthly_capacity = disposable * (0.55 if tx["avg_net"] >= 0 else 0.45)
    max_affordable = monthly_capacity * 24
    ratio_multiplier = 1.0 if composite >= 72 else 0.78 if composite >= 57 else 0.50
    max_loan_amount = round(min(requested_amount, max_affordable) * ratio_multiplier / loan_type_risk / 10000) * 10000
    suggested_rate = (10 if composite >= 80 else 12 if composite >= 66 else 14 if composite >= 51 else 16) + (1 if loan_type_risk > 1 else 0)

    key_risks: list[str] = []
    key_strengths: list[str] = []
    for dimension in dimensions:
        if dimension["score"] < 48:
            key_risks.append(f"{dimension['name']}: {dimension['signal']}")
        if dimension["score"] >= 74:
            key_strengths.append(f"{dimension['name']}: {dimension['signal']}")

    if affordability_ratio > 6:
        key_risks.append("Requested amount exceeds 6x monthly income")
    if dscr > 0.55:
        key_risks.append(f"Estimated installment consumes {round(dscr * 100)}% of disposable income")
    if status != "Active":
        key_risks.append(f"Account status: {status}")
    if overdue_count:
        key_risks.append("Existing overdue loan on portfolio")
    if active_balance > _number(member.savings) * 3:
        key_risks.append("Outstanding loan exposure is high relative to savings")
    if tx["flagged_count"]:
        key_risks.append(f"{tx['flagged_count']} recent transaction anomaly flag(s)")
    if data_confidence < 65:
        key_risks.append("Limited recent transaction evidence; manual review recommended")
    if profile.completed_loans > 0:
        key_strengths.append(f"{profile.completed_loans} loan(s) repaid without default")
    if len(guarantors) >= 2:
        key_strengths.append("Dual guarantor coverage")
    if tx["avg_net"] > 0 and tx["month_count"] >= 3:
        key_strengths.append("Recent transaction flow is net positive")
    if data_confidence >= 80:
        key_strengths.append("High scoring confidence from recent data coverage")

    result = {
        "composite": composite,
        "ruleComposite": rule_composite,
        "trendAdjustment": trend_adjustment,
        "repaymentLikelihood": repayment_likelihood,
        "defaultRisk": default_risk,
        "affordabilityRatio": affordability_ratio,
        "delinquencyRisk90d": delinquency_risk_90d,
        "recommendation": recommendation,
        "maxLoanAmount": int(max_loan_amount),
        "suggestedRate": suggested_rate,
        "dimensions": dimensions,
        "keyRisks": key_risks[:4],
        "keyStrengths": key_strengths[:4],
        "modelVersion": MODEL_VERSION,
        "historyCount": len(history),
        "dataConfidence": data_confidence,
        "activeExposure": int(active_balance),
        "activePrincipal": int(active_principal),
        "estimatedInstallment": int(estimated_installment),
    }

    if persist:
        event = LoanScoreEvent(
            member_id=member_id,
            requested_amount=requested_amount,
            loan_type=loan_type,
            composite=composite,
            repayment_likelihood=repayment_likelihood,
            default_risk=default_risk,
            recommendation=recommendation,
            model_version=MODEL_VERSION,
            dimensions_json=json.dumps(dimensions),
            key_risks_json=json.dumps(result["keyRisks"]),
            key_strengths_json=json.dumps(result["keyStrengths"]),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        result["scoreEventId"] = event.id
        result["scoredAt"] = event.created_at.isoformat()

    return result

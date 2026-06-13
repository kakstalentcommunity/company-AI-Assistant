from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.models import AnomalyFlag, Member, Transaction


def _money(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def detect_transaction_anomalies(db: Session) -> dict[str, dict[str, str]]:
    transactions = db.query(Transaction).all()
    members = {member.id: member for member in db.query(Member).all()}

    by_member_day: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    by_ref: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        by_member_day[(transaction.member_id, transaction.date)].append(transaction)
        by_ref[transaction.ref].append(transaction)

    anomalies: dict[str, dict[str, str]] = {}

    for transaction in transactions:
        reasons: list[str] = []
        amount = _money(transaction.amount)
        member = members.get(transaction.member_id)
        savings = _money(member.savings) if member else 0
        same_day = by_member_day[(transaction.member_id, transaction.date)]
        same_day_total = sum(_money(item.amount) for item in same_day)
        category = (transaction.category or "").lower()
        channel = (transaction.channel or "").lower()
        tx_type = (transaction.type or "").lower()

        if tx_type == "debit" and amount >= 500_000:
            reasons.append("High-value debit exceeds KES 500K")
        elif tx_type == "debit" and amount >= 250_000:
            reasons.append("Large debit exceeds KES 250K")

        if tx_type == "debit" and savings and amount > savings * 0.60:
            reasons.append("Debit is more than 60% of member savings balance")

        if len(same_day) >= 4:
            reasons.append(f"{len(same_day)} same-day transactions for this member")

        if same_day_total >= 750_000:
            reasons.append("Same-day transaction velocity exceeds KES 750K")

        if "withdraw" in category and channel in {"cash", "agent"} and amount >= 150_000:
            reasons.append("Large withdrawal through higher-risk channel")

        if len(by_ref[transaction.ref]) > 1:
            reasons.append("Duplicate transaction reference detected")

        if not reasons:
            continue

        level = "high" if any(
            marker in " ".join(reasons).lower()
            for marker in ["500k", "60%", "750k", "duplicate"]
        ) else "medium"
        anomalies[transaction.id] = {
            "level": level,
            "reason": "; ".join(reasons[:3]),
        }

    return anomalies


def sync_anomaly_flags(db: Session) -> None:
    anomalies = detect_transaction_anomalies(db)
    existing = {
        flag.transaction_id: flag
        for flag in db.query(AnomalyFlag).all()
    }

    for transaction_id, payload in anomalies.items():
        flag = existing.get(transaction_id)
        if flag:
            flag.level = payload["level"]
            flag.reason = payload["reason"]
        else:
            db.add(
                AnomalyFlag(
                    transaction_id=transaction_id,
                    level=payload["level"],
                    reason=payload["reason"],
                )
            )

    for transaction_id, flag in existing.items():
        if transaction_id not in anomalies:
            db.delete(flag)

    db.commit()

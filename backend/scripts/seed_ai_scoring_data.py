from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine
from app.models.models import Loan, Member, MemberProfile, Transaction
from app.services.fraud import sync_anomaly_flags
from app.services.scoring import score_member_loan


def money(value: int | float | str) -> Decimal:
    return Decimal(str(value))


def iso_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).date().isoformat()


def upsert_member(db, data: dict) -> None:
    member = db.get(Member, data["id"])
    if member:
        for key, value in data.items():
            setattr(member, key, value)
        return
    db.add(Member(**data))


def upsert_profile(db, data: dict) -> None:
    profile = db.get(MemberProfile, data["member_id"])
    if profile:
        for key, value in data.items():
            setattr(profile, key, value)
        return
    db.add(MemberProfile(**data))


def upsert_loan(db, data: dict) -> None:
    loan = db.get(Loan, data["id"])
    if loan:
        for key, value in data.items():
            setattr(loan, key, value)
        return
    db.add(Loan(**data))


def upsert_transaction(db, data: dict) -> None:
    transaction = db.get(Transaction, data["id"])
    if transaction:
        for key, value in data.items():
            setattr(transaction, key, value)
        return
    db.add(Transaction(**data))


def transaction_rows(member_id: str, prefix: str, monthly_credits: list[int], monthly_debits: list[int]) -> list[dict]:
    rows: list[dict] = []
    for index, (credit, debit) in enumerate(zip(monthly_credits, monthly_debits), start=1):
        days_ago = (len(monthly_credits) - index) * 30 + 6
        rows.append(
            {
                "id": f"{prefix}-SAL-{index:02d}",
                "member_id": member_id,
                "amount": money(credit),
                "type": "Credit",
                "category": "Salary Deposit" if credit >= 80_000 else "Business Sales",
                "date": iso_days_ago(days_ago),
                "ref": f"{prefix}-SAL-REF-{index:02d}",
                "channel": "Bank Transfer" if credit >= 80_000 else "M-Pesa",
            }
        )
        rows.append(
            {
                "id": f"{prefix}-EXP-{index:02d}",
                "member_id": member_id,
                "amount": money(debit),
                "type": "Debit",
                "category": "Household Expenses",
                "date": iso_days_ago(max(days_ago - 10, 1)),
                "ref": f"{prefix}-EXP-REF-{index:02d}",
                "channel": "M-Pesa",
            }
        )
    return rows


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        members = [
            {
                "id": "AIS-LOW",
                "name": "Amina Otieno",
                "email": "amina.ai-test@example.com",
                "savings": money(850_000),
                "loans": money(45_000),
                "status": "Active",
                "joined": "2023-02-14",
                "shares": 3200,
            },
            {
                "id": "AIS-MED",
                "name": "Brian Mwangi",
                "email": "brian.ai-test@example.com",
                "savings": money(180_000),
                "loans": money(120_000),
                "status": "Active",
                "joined": "2024-08-03",
                "shares": 950,
            },
            {
                "id": "AIS-HIGH",
                "name": "Caroline Wanjiku",
                "email": "caroline.ai-test@example.com",
                "savings": money(55_000),
                "loans": money(255_000),
                "status": "Active",
                "joined": "2025-11-20",
                "shares": 420,
            },
        ]
        for member in members:
            upsert_member(db, member)

        profiles = [
            {
                "member_id": "AIS-LOW",
                "employer": "Nairobi County Health Services",
                "employer_type": "Government",
                "estimated_monthly_income": money(165_000),
                "mpesa_monthly_inflows": json.dumps([158000, 162000, 166000, 171000, 168000, 174000]),
                "guarantors": json.dumps(["MBR-012", "MBR-044"]),
                "monthly_expenses": money(72_000),
                "completed_loans": 4,
                "defaulted_loans": 0,
            },
            {
                "member_id": "AIS-MED",
                "employer": "Mwangi Agro Supplies",
                "employer_type": "Self-Employed",
                "estimated_monthly_income": money(92_000),
                "mpesa_monthly_inflows": json.dumps([74000, 108000, 82000, 98000, 76000, 103000]),
                "guarantors": json.dumps(["MBR-018"]),
                "monthly_expenses": money(54_000),
                "completed_loans": 1,
                "defaulted_loans": 0,
            },
            {
                "member_id": "AIS-HIGH",
                "employer": "Market Stall Operations",
                "employer_type": "Informal",
                "estimated_monthly_income": money(58_000),
                "mpesa_monthly_inflows": json.dumps([42000, 78000, 29000, 66000, 36000, 51000]),
                "guarantors": json.dumps([]),
                "monthly_expenses": money(49_000),
                "completed_loans": 0,
                "defaulted_loans": 2,
            },
            {
                "member_id": "1234",
                "employer": "Kisumu Teachers Cooperative",
                "employer_type": "Formal",
                "estimated_monthly_income": money(95_000),
                "mpesa_monthly_inflows": json.dumps([88000, 91000, 94000, 97000, 96000, 99000]),
                "guarantors": json.dumps(["AIS-LOW"]),
                "monthly_expenses": money(48_000),
                "completed_loans": 2,
                "defaulted_loans": 0,
            },
            {
                "member_id": "1235",
                "employer": "Jango Wholesale Traders",
                "employer_type": "Self-Employed",
                "estimated_monthly_income": money(210_000),
                "mpesa_monthly_inflows": json.dumps([180000, 205000, 235000, 220000, 245000, 260000]),
                "guarantors": json.dumps(["1234", "AIS-MED"]),
                "monthly_expenses": money(118_000),
                "completed_loans": 3,
                "defaulted_loans": 0,
            },
        ]
        for profile in profiles:
            upsert_profile(db, profile)

        loans = [
            {
                "id": "AIS-LN-LOW-01",
                "member_id": "AIS-LOW",
                "amount": money(120_000),
                "balance": money(45_000),
                "rate": money(12),
                "issued": iso_days_ago(150),
                "due": iso_days_ago(-210),
                "status": "Performing",
                "type": "Development",
            },
            {
                "id": "AIS-LN-MED-01",
                "member_id": "AIS-MED",
                "amount": money(180_000),
                "balance": money(120_000),
                "rate": money(14),
                "issued": iso_days_ago(100),
                "due": iso_days_ago(-260),
                "status": "Performing",
                "type": "Business",
            },
            {
                "id": "AIS-LN-HIGH-01",
                "member_id": "AIS-HIGH",
                "amount": money(260_000),
                "balance": money(255_000),
                "rate": money(16),
                "issued": iso_days_ago(220),
                "due": iso_days_ago(18),
                "status": "Overdue",
                "type": "Emergency",
            },
        ]
        for loan in loans:
            upsert_loan(db, loan)

        rows = []
        rows.extend(transaction_rows("AIS-LOW", "AISLOW", [158000, 162000, 166000, 171000, 168000, 174000], [52000, 57000, 55000, 61000, 59000, 60000]))
        rows.extend(transaction_rows("AIS-MED", "AISMED", [74000, 108000, 82000, 98000, 76000, 103000], [59000, 72000, 65000, 80000, 70000, 76000]))
        rows.extend(transaction_rows("AIS-HIGH", "AISHIGH", [42000, 78000, 29000, 66000, 36000, 51000], [53000, 91000, 62000, 88000, 70000, 145000]))
        rows.append(
            {
                "id": "AISHIGH-CASH-01",
                "member_id": "AIS-HIGH",
                "amount": money(265_000),
                "type": "Debit",
                "category": "Cash Withdrawal",
                "date": iso_days_ago(9),
                "ref": "AISHIGH-CASH-REF-01",
                "channel": "Agent",
            }
        )
        rows.extend(transaction_rows("1234", "EX1234", [88000, 91000, 94000, 97000, 96000, 99000], [41000, 43000, 45000, 47000, 44000, 46000]))
        rows.extend(transaction_rows("1235", "EX1235", [180000, 205000, 235000, 220000, 245000, 260000], [96000, 108000, 112000, 125000, 118000, 130000]))
        for row in rows:
            upsert_transaction(db, row)

        db.commit()
        sync_anomaly_flags(db)

        scenarios = [
            ("AIS-LOW", 300_000, "Development"),
            ("AIS-MED", 250_000, "Business"),
            ("AIS-HIGH", 180_000, "Emergency"),
            ("1234", 120_000, "Education"),
            ("1235", 650_000, "Business"),
        ]
        print("Seeded AI loan scoring data.")
        for member_id, amount, loan_type in scenarios:
            result = score_member_loan(db, member_id, amount, loan_type, persist=False)
            print(
                f"{member_id}: composite={result['composite']} "
                f"recommendation={result['recommendation']} "
                f"risk={result['defaultRisk']} confidence={result['dataConfidence']}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    seed()

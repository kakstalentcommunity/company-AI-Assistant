from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    savings: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    loans: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Active")
    joined: Mapped[str] = mapped_column(String(20), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])
    loan_records: Mapped[list[Loan]] = relationship("Loan", back_populates="member", cascade="all, delete-orphan")
    transaction_records: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="member",
        cascade="all, delete-orphan",
    )
    profile: Mapped[MemberProfile | None] = relationship(
        "MemberProfile",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(String(30), primary_key=True, index=True)
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    issued: Mapped[str] = mapped_column(String(20), nullable=False)
    due: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    member: Mapped[Member] = relationship("Member", back_populates="loan_records")

    __table_args__ = (
        Index("ix_loans_member_issued_id", "member_id", "issued", "id"),
        Index("ix_loans_status_due", "status", "due"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(30), primary_key=True, index=True)
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ref: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    mpesa_receipt_number: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mpesa_phone_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    mpesa_checkout_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mpesa_merchant_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mpesa_result_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    mpesa_result_description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mpesa_raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    member: Mapped[Member] = relationship("Member", back_populates="transaction_records")
    anomaly_flag: Mapped[AnomalyFlag | None] = relationship(
        "AnomalyFlag",
        back_populates="transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_transactions_member_date_id", "member_id", "date", "id"),
        Index("ix_transactions_type_date", "type", "date"),
    )


class TransactionRequest(Base):
    __tablename__ = "transaction_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    loan_id: Mapped[str | None] = mapped_column(String(30), ForeignKey("loans.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ref: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    mpesa_receipt_number: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mpesa_phone_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    mpesa_checkout_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mpesa_merchant_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mpesa_result_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    mpesa_result_description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mpesa_raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Pending", index=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    member: Mapped[Member] = relationship("Member")
    loan: Mapped[Loan | None] = relationship("Loan")
    requester: Mapped[User] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewed_by_user_id])


class MpesaPayment(Base):
    __tablename__ = "mpesa_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_request_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("transaction_requests.id"), nullable=True, index=True)
    member_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("members.id"), nullable=True, index=True)
    loan_id: Mapped[str | None] = mapped_column(String(30), ForeignKey("loans.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    receipt_number: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    bill_ref_number: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    transaction_time: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    merchant_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    checkout_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    result_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    result_description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Received", index=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    transaction_request: Mapped[TransactionRequest | None] = relationship("TransactionRequest")
    member: Mapped[Member | None] = relationship("Member")
    loan: Mapped[Loan | None] = relationship("Loan")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    month: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    savings: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    loans: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    repayments: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)


class MemberProfile(Base):
    __tablename__ = "member_profiles"

    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.id"), primary_key=True)
    employer: Mapped[str] = mapped_column(String(255), nullable=False)
    employer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    estimated_monthly_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    mpesa_monthly_inflows: Mapped[str] = mapped_column(Text, nullable=False)
    guarantors: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    completed_loans: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    defaulted_loans: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    member: Mapped[Member] = relationship("Member", back_populates="profile")


class AnomalyFlag(Base):
    __tablename__ = "anomaly_flags"

    transaction_id: Mapped[str] = mapped_column(String(30), ForeignKey("transactions.id"), primary_key=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)

    transaction: Mapped[Transaction] = relationship("Transaction", back_populates="anomaly_flag")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    tokens: Mapped[list[AuthToken]] = relationship(
        "AuthToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped[User] = relationship("User", back_populates="tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user: Mapped[User] = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    message: Mapped[str] = mapped_column(String(700), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="info", index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])
    created_by: Mapped[User | None] = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    before_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    after_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    actor: Mapped[User | None] = relationship("User")


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_rate_limit_events_key_created", "key", "created_at"),
    )


class MembershipApplication(Base):
    __tablename__ = "membership_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    national_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending", index=True)
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    member_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("members.id"), nullable=True, index=True)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewed_by])
    member: Mapped[Member | None] = relationship("Member")


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    term_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending", index=True)
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    loan_id: Mapped[str | None] = mapped_column(String(30), ForeignKey("loans.id"), nullable=True, index=True)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewed_by])
    member: Mapped[Member] = relationship("Member")
    loan: Mapped[Loan | None] = relationship("Loan")

    __table_args__ = (
        Index("ix_loan_applications_member_created_id", "member_id", "created_at", "id"),
        Index("ix_loan_applications_status_created", "status", "created_at"),
    )


class LoanScoreEvent(Base):
    __tablename__ = "loan_score_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.id"), nullable=False, index=True)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    loan_type: Mapped[str] = mapped_column(String(100), nullable=False)
    composite: Mapped[int] = mapped_column(Integer, nullable=False)
    repayment_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    default_risk: Mapped[str] = mapped_column(String(50), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    dimensions_json: Mapped[str] = mapped_column(Text, nullable=False)
    key_risks_json: Mapped[str] = mapped_column(Text, nullable=False)
    key_strengths_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    member: Mapped[Member] = relationship("Member")


class ProductAnalyticsEvent(Base):
    __tablename__ = "product_analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    funnel_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    funnel_step: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    device: Mapped[str] = mapped_column(String(30), nullable=False, default="Web", index=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    properties_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped[User | None] = relationship("User")


class ProductUsageDailyMetric(Base):
    __tablename__ = "product_usage_daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    metric_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    dau: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mau: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_session_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounce_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    retention_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    active_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ProductAnalyticsAlert(Base):
    __tablename__ = "product_analytics_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    metric: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    current_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Open", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class ProductAnalyticsInsight(Base):
    __tablename__ = "product_analytics_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    narrative: Mapped[str] = mapped_column(String(700), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

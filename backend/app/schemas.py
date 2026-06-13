import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemberCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    user_id: int | None = Field(default=None, alias="userId", ge=1)
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    savings: float = Field(default=0, ge=0)
    loans: float = Field(default=0, ge=0)
    status: str = Field(default="Active", pattern=r"^(Active|Inactive|Suspended)$")
    joined: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    shares: int = Field(default=0, ge=0)


class MemberUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int | None = Field(default=None, alias="userId", ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = Field(default=None, min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    savings: float | None = Field(default=None, ge=0)
    loans: float | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(Active|Inactive|Suspended)$")
    joined: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    shares: int | None = Field(default=None, ge=0)


class LoanCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    member_id: str = Field(alias="memberId", max_length=20)
    amount: float = Field(gt=0)
    balance: float = Field(ge=0)
    rate: float = Field(ge=0, le=100)
    issued: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    due: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: str = Field(pattern=r"^(Active|Overdue|Completed|Pending)$")
    type: str = Field(min_length=2, max_length=100)


class LoanUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    member_id: str | None = Field(default=None, alias="memberId", max_length=20)
    amount: float | None = Field(default=None, gt=0)
    balance: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0, le=100)
    issued: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    due: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: str | None = Field(default=None, pattern=r"^(Active|Overdue|Completed|Pending)$")
    type: str | None = Field(default=None, min_length=2, max_length=100)


class TransactionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    member_id: str = Field(alias="memberId", max_length=20)
    amount: float = Field(gt=0)
    type: str = Field(pattern=r"^(Credit|Debit)$")
    category: str = Field(min_length=2, max_length=100)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ref: str = Field(min_length=2, max_length=100)
    channel: str = Field(min_length=2, max_length=100)
    mpesa_receipt_number: str | None = Field(default=None, alias="mpesaReceiptNumber", max_length=100)
    mpesa_phone_number: str | None = Field(default=None, alias="mpesaPhoneNumber", max_length=30)
    mpesa_checkout_request_id: str | None = Field(default=None, alias="mpesaCheckoutRequestId", max_length=100)
    mpesa_merchant_request_id: str | None = Field(default=None, alias="mpesaMerchantRequestId", max_length=100)
    mpesa_result_code: str | None = Field(default=None, alias="mpesaResultCode", max_length=20)
    mpesa_result_description: str | None = Field(default=None, alias="mpesaResultDescription", max_length=255)


class TransactionUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    member_id: str | None = Field(default=None, alias="memberId", max_length=20)
    amount: float | None = Field(default=None, gt=0)
    type: str | None = Field(default=None, pattern=r"^(Credit|Debit)$")
    category: str | None = Field(default=None, min_length=2, max_length=100)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    ref: str | None = Field(default=None, min_length=2, max_length=100)
    channel: str | None = Field(default=None, min_length=2, max_length=100)
    mpesa_receipt_number: str | None = Field(default=None, alias="mpesaReceiptNumber", max_length=100)
    mpesa_phone_number: str | None = Field(default=None, alias="mpesaPhoneNumber", max_length=30)
    mpesa_checkout_request_id: str | None = Field(default=None, alias="mpesaCheckoutRequestId", max_length=100)
    mpesa_merchant_request_id: str | None = Field(default=None, alias="mpesaMerchantRequestId", max_length=100)
    mpesa_result_code: str | None = Field(default=None, alias="mpesaResultCode", max_length=20)
    mpesa_result_description: str | None = Field(default=None, alias="mpesaResultDescription", max_length=255)


class TransactionRequestCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    loan_id: str | None = Field(default=None, alias="loanId", max_length=30)
    type: str = Field(pattern=r"^(Credit|Debit)$")
    amount: float = Field(gt=0)
    category: str = Field(min_length=2, max_length=100)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ref: str = Field(min_length=2, max_length=100)
    channel: str = Field(min_length=2, max_length=100)
    mpesa_receipt_number: str | None = Field(default=None, alias="mpesaReceiptNumber", max_length=100)
    mpesa_phone_number: str | None = Field(default=None, alias="mpesaPhoneNumber", max_length=30)
    mpesa_checkout_request_id: str | None = Field(default=None, alias="mpesaCheckoutRequestId", max_length=100)
    mpesa_merchant_request_id: str | None = Field(default=None, alias="mpesaMerchantRequestId", max_length=100)
    mpesa_result_code: str | None = Field(default=None, alias="mpesaResultCode", max_length=20)
    mpesa_result_description: str | None = Field(default=None, alias="mpesaResultDescription", max_length=255)


class TransactionRequestReview(BaseModel):
    status: str = Field(pattern=r"^(Approved|Rejected)$")
    review_note: str | None = Field(default=None, alias="reviewNote", max_length=500)


class MpesaLoanRepaymentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    loan_id: str = Field(alias="loanId", min_length=2, max_length=30)
    amount: float = Field(gt=0)
    phone_number: str | None = Field(default=None, alias="phoneNumber", max_length=30)
    mpesa_receipt_number: str = Field(alias="mpesaReceiptNumber", min_length=2, max_length=100)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class MpesaStkPushCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    purpose: str = Field(pattern=r"^(loan_repayment|savings_deposit|transaction)$")
    amount: float = Field(gt=0)
    phone_number: str = Field(alias="phoneNumber", min_length=9, max_length=30)
    loan_id: str | None = Field(default=None, alias="loanId", max_length=30)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    transaction_type: str = Field(default="Credit", alias="transactionType", pattern=r"^(Credit|Debit)$")
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class LoanScoreRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    member_id: str | None = Field(default=None, alias="memberId")
    loan_amount: float | None = Field(default=None, alias="loanAmount", gt=0)
    loan_type: str = Field(default="Business", alias="loanType", max_length=100)
    persist: bool = True


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        checks = [
            bool(re.search(r"[a-z]", value)),
            bool(re.search(r"[A-Z]", value)),
            bool(re.search(r"\d", value)),
            bool(re.search(r"[^A-Za-z0-9]", value)),
        ]
        if sum(checks) < 3:
            raise ValueError("Password must include at least three of: lowercase, uppercase, number, symbol")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return SignupRequest.strong_password(value)


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|staff)$")
    is_active: bool | None = Field(default=None, alias="isActive")


class NotificationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId", ge=1)
    title: str = Field(min_length=2, max_length=140)
    message: str = Field(min_length=2, max_length=700)
    type: str = Field(default="info", pattern=r"^(info|success|warning|danger)$")
    entity_type: str = Field(default="", alias="entityType", max_length=80)
    entity_id: str = Field(default="", alias="entityId", max_length=80)


class AdminUserCreate(SignupRequest):
    role: str = "staff"


class MembershipApplicationCreate(BaseModel):
    phone: str = Field(default="", max_length=50)
    national_id: str = Field(default="", alias="nationalId", max_length=100)
    address: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=500)


class ApplicationReview(BaseModel):
    status: str = Field(pattern=r"^(Approved|Rejected)$")
    notes: str = Field(default="", max_length=500)


class LoanApplicationCreate(BaseModel):
    amount: float = Field(gt=0)
    type: str = Field(default="Business", max_length=100)
    purpose: str = Field(default="", max_length=500)
    term_months: int = Field(default=12, alias="termMonths", ge=1, le=84)


class ProductAnalyticsEventCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=6, max_length=80)
    event_name: str = Field(alias="eventName", min_length=2, max_length=100)
    feature: str = Field(default="general", max_length=80)
    funnel_name: str | None = Field(default=None, alias="funnelName", max_length=80)
    funnel_step: str | None = Field(default=None, alias="funnelStep", max_length=80)
    device: str = Field(default="Web", pattern=r"^(Android|iOS|Web|USSD)$")
    path: str = Field(default="", max_length=255)
    duration_seconds: int | None = Field(default=None, alias="durationSeconds", ge=0, le=86400)
    properties: dict = Field(default_factory=dict)

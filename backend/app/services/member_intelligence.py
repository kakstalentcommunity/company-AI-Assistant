from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


# --- Table name constants ---
MEMBER_TABLE = "cr_bo_accounts"
LOAN_TABLE = "cr_loans"
ALAZAR_TABLE = "Alazar"
ITEM_TRACKING_TABLE = "Item_Tracking_lines"
LOAN_DISBURSEMENT_TABLE = "Loan_disbursement_dates"
PAYSLIP_DETAILS_TABLE = "Payslip_details"
STOCK_TAKING_HEADER_TABLE = "Stock_Taking_Setup_Header"
ADDRESS_UPDATE_TABLE = "address_update"
ADVANCE_LOANS_TABLE = "advance_loans"
AHADI_PAYE_TABLE = "ahadi_paye"
AIRTEL_DISCOUNTS_TABLE = "airtel_discounts"
AIRTIME_MERCHANT_LOGS_TABLE = "airtime_merchant_logs"
ALL_NATIONSDETAILS_TABLE = "all_nationsdetails"
ASSESSMENT_BOOKS_TABLE = "assessment_books"
ATTENDANCE_LINES_TABLE = "attendance_lines"
BARTER_TRANSACTIONS_TABLE = "barter_transactions"
BIODATA_RAINFOREST_TABLE = "biodata_rainforest"
BOOK_ASSIGNMENTS_TABLE = "book_assignments"
BOOKS_TABLE = "books"
BRAUN_TABLE = "braun"
BU_COMMITEES_TABLE = "bu_commitees"
BU_REQUISITION_HEADER_TABLE = "bu_requisition_header"
BU_REQUISITION_LINES_TABLE = "bu_requisition_lines"
BUDGET_TABLE = "budget"
BUDGET_ALLOCATIONS_TABLE = "budget_allocations"
BUDGET_LINE_TABLE = "budget_line"
CALENDER_OF_EVENTS_TABLE = "calender_of_events"
CASH_FLOW_FORECAST_TABLE = "cash_flow_forecast"
CASH_FORECAST_ALLOCATIONS_TABLE = "cash_forecast_allocations"
CASH_FORECAST_LINE_TABLE = "cash_forecast_line"
CASH_RECEIPTS_TABLE = "cash_receipts"
CAT_QUESTIONS_TABLE = "cat_questions"
CATEGORY_TYPES_TABLE = "category_types"
CBK_TRANSFERS_TABLE = "cbk_transfers"
CBO_MEMBERS_TABLE = "cbo_members"
CFT_INCOME_ACCRUAL_LINES_TABLE = "cft_income_accrual_lines"
CFT_INCOME_ACCRUALS_TABLE = "cft_income_accruals"
CI_SESSIONS_TABLE = "ci_sessions"
CLOSING_INTEREST_SIGINON_TABLE = "closing_interest_siginon"
CO_IMPREST_REQUISITION_LINES_TABLE = "co_imprest_requisition_lines"
CO_IMPREST_REQUISITIONS_TABLE = "co_imprest_requisitions"
CO_IMPREST_SURRENDER_TABLE = "co_imprest_surrender"
CO_IMPREST_SURRENDER_LINES_TABLE = "co_imprest_surrender_lines"
CO_IMPREST_SURRENDER_LINESOLD_TABLE = "co_imprest_surrender_linesold"
CO_IMPREST_SURRENDEROLD_TABLE = "co_imprest_surrenderold"
COA_GROUPS_TABLE = "coa_groups"
COA_SUB_GROUPS_TABLE = "coa_sub_groups"
COOP_LINES_TABLE = "coop_lines"
CORRECTION_DEPOSITS_TABLE = "correction_deposits"
CR_LOAN_AMOUNT_BANDS_TABLE = "cr_Loan_amount_bands"
CR_ACCOUNT_TYPES_TABLE = "cr_account_types"
CR_ACCRUAL_HEADER_TABLE = "cr_accrual_header"
CR_ACCRUAL_LINE_TABLE = "cr_accrual_line"
CR_ARREARS_OFFSET_TABLE = "cr_arrears_offset"
CR_BANKING_AGENTS_TABLE = "cr_banking_agents"
CR_BO_ACCOUNTS_NOS_TABLE = "cr_bo_accounts_nos"
CR_BO_APPLICATIONS_TABLE = "cr_bo_applications"
CR_BO_APPLICATIONS_OLD_TABLE = "cr_bo_applications_old"
CR_BO_CHARGES_TABLE = "cr_bo_charges"
CR_BO_DEPARTMENTS_TABLE = "cr_bo_departments"
CR_BO_DEPOSIT_CLASSIFICATION_TABLE = "cr_bo_deposit_classification"
CR_BO_GENERAL_SETUP_TABLE = "cr_bo_general_setup"
CR_BO_INSIDER_BORROWERS_TABLE = "cr_bo_insider_borrowers"
CR_BO_LEDGER_ENTRY_TABLE = "cr_bo_ledger_entry"
CR_BO_MOBILE_APPLICATIONS_TABLE = "cr_bo_mobile_applications"
CR_BO_POSTING_GROUP_TABLE = "cr_bo_posting_group"
CR_BOSA_STANDING_LINES_TABLE = "cr_bosa_standing_lines"
CR_BUSINESS_TYPES_TABLE = "cr_business_types"
CR_CHECKOFF_ADVICE_TABLE = "cr_checkoff_advice"
CR_CHECKOFF_ADVICE_DETAILS_TABLE = "cr_checkoff_advice_details"
CR_CHECKOFF_ADVICE_IMPORTS_TABLE = "cr_checkoff_advice_imports"
CR_DIVIDEND_WITHDRAWAL_CHARGES_TABLE = "cr_dividend_withdrawal_charges"
CR_DIVIDENDS_MANUAL_APPRAISAL_TABLE = "cr_dividends_manual_appraisal"
CR_EMPLOYER_PAYROLL_GROUPS_TABLE = "cr_employer_payroll_groups"
CR_EMPLOYERS_TABLE = "cr_employers"
CR_EWALLET_TRANSFER_CHARGES_TABLE = "cr_ewallet_transfer_charges"
CR_FIXED_DEPOSITS_TABLE = "cr_fixed_deposits"
CR_FO_INTEREST_HEADER_TABLE = "cr_fo_interest_header"
CR_FO_INTEREST_LINES_TABLE = "cr_fo_interest_lines"
CR_FOSA_ACCRUAL_HEADER_TABLE = "cr_fosa_accrual_header"
CR_FOSA_ACCRUAL_LINE_TABLE = "cr_fosa_accrual_line"
CR_FOSA_STANDING_LINES_TABLE = "cr_fosa_standing_lines"
CR_FOSA_TRANS_CHARGES_TABLE = "cr_fosa_trans_charges"
CR_CHECKOFF_ADVICE_LINE_TABLE = "cr_checkoff_advice_line"
CR_CHECKOFF_ALLOCATIONS_TABLE = "cr_checkoff_allocations"
CR_CHECKOFF_DEFAULTERS_TABLE = "cr_checkoff_defaulters"
CR_CHECKOFF_DEFAULTERS_HEADER_TABLE = "cr_checkoff_defaulters_header"
CR_CHECKOFF_DEFAULTERS_SIMUNYE_TABLE = "cr_checkoff_defaulters_simunye"
CR_CHECKOFF_HEADER_TABLE = "cr_checkoff_header"
CR_CHECKOFF_LINE_TABLE = "cr_checkoff_line"
CR_CHECKOFF_STATISTICS_TABLE = "cr_checkoff_statistics"
CR_CHECKOFF_SUMMARY_TABLE = "cr_checkoff_summary"

# --- Lookup column tuples ---
MEMBER_LOOKUP_COLUMNS = (
    "member_number", "bo_account_no", "account_name", "full_name",
    "first_name", "middle_name", "last_name", "id_number",
    "passport_number", "mobile_number", "secondary_mobile_number", "email_address",
)

LOAN_LOOKUP_COLUMNS = (
    "member_number", "loan_number", "application_no", "full_name", "id_number", "mobile_number",
)

ALAZAR_LOOKUP_COLUMNS = ("adm_no", "mobile_number")

ITEM_TRACKING_LOOKUP_COLUMNS = (
    "Stocktake_Code", "Item_Code", "Package_Code", "Location_Code", "Description", "entry_type",
)

LOAN_DISBURSEMENT_LOOKUP_COLUMNS = ("Loan_no",)

PAYSLIP_DETAILS_LOOKUP_COLUMNS = (
    "employer_code", "payroll_number", "member_name", "bank_name", "bank_acc_no", "id_number",
)

STOCK_TAKING_HEADER_LOOKUP_COLUMNS = (
    "Code", "Description", "Created_By", "Type_of_Stock_Taking", "lead_by", "Status", "dimension_code",
)

ADDRESS_UPDATE_LOOKUP_COLUMNS = ("mno", "address_")

ADVANCE_LOANS_LOOKUP_COLUMNS = ("user_id", "teacher_id", "first_name", "middle_name", "last_name", "status")

AHADI_PAYE_LOOKUP_COLUMNS = ("staff_no",)

AIRTEL_DISCOUNTS_LOOKUP_COLUMNS = ("discount_id",)

AIRTIME_MERCHANT_LOGS_LOOKUP_COLUMNS = ("type", "loaded_by")

ALL_NATIONSDETAILS_LOOKUP_COLUMNS = ("member_no", "group_code")

ASSESSMENT_BOOKS_LOOKUP_COLUMNS = ("class_name", "subject_name", "file_name", "file_type")

ATTENDANCE_LINES_LOOKUP_COLUMNS = ("admin_no", "full_name", "status", "Month", "Year")

BARTER_TRANSACTIONS_LOOKUP_COLUMNS = (
    "document_no", "source_doc_no", "dest_doc_no", "account_no", "account_name",
    "approval_status", "user", "description", "invoice_no", "bill_no",
)

BIODATA_RAINFOREST_LOOKUP_COLUMNS = (
    "member_number", "id", "phone", "employer_code", "employer_description", "email", "member_status",
)

BOOK_ASSIGNMENTS_LOOKUP_COLUMNS = ("book_no", "book_id", "admission_no", "student_name", "student_class", "assigned_by")

BOOKS_LOOKUP_COLUMNS = ("title", "author", "book_no", "class", "subject", "status", "location")

BRAUN_LOOKUP_COLUMNS = ("id_no",)
BU_COMMITEES_LOOKUP_COLUMNS = ("commitee_code", "commitee_name")
BU_REQUISITION_HEADER_LOOKUP_COLUMNS = ("requisition_no", "commitee_code", "commitee_name", "description", "venue")
BU_REQUISITION_LINES_LOOKUP_COLUMNS = ("requisition_no", "item_code", "item")
BUDGET_LOOKUP_COLUMNS = ("no", "account_no", "account_name", "document_no", "global_dimension_code1", "global_dimension_code2", "checkoff_account")
BUDGET_ALLOCATIONS_LOOKUP_COLUMNS = ("no", "transaction_type", "receipt_category", "gl_account", "loan_no", "account_no", "account_name", "fosa_account")
BUDGET_LINE_LOOKUP_COLUMNS = ("no", "payroll_number", "account_no", "account_name", "transaction_type", "description", "loan_number", "employer_code", "id_number", "fosa_account", "reference")
CALENDER_OF_EVENTS_LOOKUP_COLUMNS = ("activity",)
CASH_FLOW_FORECAST_LOOKUP_COLUMNS = ("no", "account_no", "account_name", "document_no", "global_dimension_code1", "global_dimension_code2", "checkoff_account")
CASH_FORECAST_ALLOCATIONS_LOOKUP_COLUMNS = ("no", "transaction_type", "receipt_category", "gl_account", "loan_no", "account_no", "account_name", "fosa_account")
CASH_FORECAST_LINE_LOOKUP_COLUMNS = ("no", "payroll_number", "account_no", "account_name", "transaction_type", "description", "loan_number", "employer_code", "id_number", "fosa_account", "reference")
CASH_RECEIPTS_LOOKUP_COLUMNS = ("recp_no",)
CAT_QUESTIONS_LOOKUP_COLUMNS = ("exam_code", "subject_code", "class_code", "teacher_id", "file_no")
CATEGORY_TYPES_LOOKUP_COLUMNS = ("sub_code", "type_code", "type_name")
CBK_TRANSFERS_LOOKUP_COLUMNS = ("document_no", "dest_doc_no", "source_doc_no", "cbk_source_code", "cbk_destination_code", "external_document_no", "transaction_type", "user")
CBO_MEMBERS_LOOKUP_COLUMNS = ("member_no", "Group_code")
CFT_INCOME_ACCRUAL_LINES_LOOKUP_COLUMNS = ("no", "client_code", "client_name", "gl_account", "activity_code", "branch_code")
CFT_INCOME_ACCRUALS_LOOKUP_COLUMNS = ("no", "account_type", "account_no", "account_name", "activity_code", "branch_code", "transaction_type", "captured_by", "posted_by")
CI_SESSIONS_LOOKUP_COLUMNS = ("session_id", "ip_address", "status")
CLOSING_INTEREST_SIGINON_LOOKUP_COLUMNS = ("id", "loan_number", "member_no")
CO_IMPREST_REQUISITION_LINES_LOOKUP_COLUMNS = ("item_code", "document_no", "gl_account_no", "votehead_code", "cheque_no", "cbk_code", "account_type", "account_no", "account_name", "payment_type")
CO_IMPREST_REQUISITIONS_LOOKUP_COLUMNS = ("document_no", "display_document_no", "staff_no", "staff_name", "user_id", "cheque_no", "cbk_code", "acc_no", "acc_no_staff", "customer_no", "client_name", "payment_type")
CO_IMPREST_SURRENDER_LOOKUP_COLUMNS = ("document_no", "display_document_no", "client_id", "client_name", "user_id", "cheque_no", "cbk_code", "acc_no", "acc_no_staff", "customer_no", "payment_type", "requisition_no")
CO_IMPREST_SURRENDER_LINES_LOOKUP_COLUMNS = ("item_name", "document_no", "gl_account_no", "votehead_code", "cheque_no", "cbk_code", "account_type", "account_no", "account_name", "payment_type")
CO_IMPREST_SURRENDER_LINESOLD_LOOKUP_COLUMNS = ("item_code", "document_no", "gl_account_no", "votehead_code", "cheque_no", "cbk_code", "surrender_doc_number")
CO_IMPREST_SURRENDEROLD_LOOKUP_COLUMNS = ("document_no", "staff_no", "staff_name", "user_id", "cheque_no", "cbk_code", "acc_no", "acc_no_staff", "surrender_doc_number")
COA_GROUPS_LOOKUP_COLUMNS = ("code", "group_name")
COA_SUB_GROUPS_LOOKUP_COLUMNS = ("code", "sub_code", "sub_group_name")
COOP_LINES_LOOKUP_COLUMNS = ("custmemoline1", "custmemoline2", "custmemoline3", "event_type")
CORRECTION_DEPOSITS_LOOKUP_COLUMNS = ("memb_number",)
CR_LOAN_AMOUNT_BANDS_LOOKUP_COLUMNS = ("code", "loan_product")
CR_ACCOUNT_TYPES_LOOKUP_COLUMNS = ("code",)
CR_ACCRUAL_HEADER_LOOKUP_COLUMNS = ("no", "captured_by", "posted_by", "accrual_type", "bo_group", "employer_code", "employer_description", "reversed_by")
CR_ACCRUAL_LINE_LOOKUP_COLUMNS = ("no", "client_code", "client_name", "loan_number", "loan_product", "gl_account", "payroll_number", "accrual_type", "action_type")
CR_ARREARS_OFFSET_LOOKUP_COLUMNS = ("loan_number", "topup_loan_number", "loan_to_offset", "client_code", "loan_product")
CR_BANKING_AGENTS_LOOKUP_COLUMNS = ("agent_number", "id_no", "phone_no", "mobile_number", "first_name", "middle_name", "last_name", "full_name", "agency_name")
CR_BO_ACCOUNTS_NOS_LOOKUP_COLUMNS = ("member_number", "mobile_number")
CR_BO_APPLICATIONS_LOOKUP_COLUMNS = ("no", "first_name", "middle_name", "last_name", "full_name", "account_name", "id_number", "passport_number", "member_number", "mobile_number", "email_address", "employer_code", "payroll_number", "bo_account_no", "referee_member_no", "referee_name")
CR_BO_APPLICATIONS_OLD_LOOKUP_COLUMNS = ("no", "first_name", "middle_name", "last_name", "full_name", "account_name", "id_number", "member_number", "mobile_number", "email_address", "employer_code", "payroll_number", "bo_account_no", "referee_member_no", "referee_name")
CR_BO_CHARGES_LOOKUP_COLUMNS = ("member_no", "doc_no", "trans_type", "loan_no")
CR_BO_DEPARTMENTS_LOOKUP_COLUMNS = ("department_code", "department_description")
CR_BO_DEPOSIT_CLASSIFICATION_LOOKUP_COLUMNS = ("member_no",)
CR_BO_GENERAL_SETUP_LOOKUP_COLUMNS = ("company_no_series", "default_customer_posting_group", "institution_founding_date")
CR_BO_INSIDER_BORROWERS_LOOKUP_COLUMNS = ("member_no", "name", "position")
CR_BO_LEDGER_ENTRY_LOOKUP_COLUMNS = ("client_code", "document_no", "loan_number", "transaction_type", "description", "user_name", "source_code", "document_type", "payment_reference", "fosa_account", "fosa_account_no", "external_document_no")
CR_BO_MOBILE_APPLICATIONS_LOOKUP_COLUMNS = ("mobile_number", "account_number", "full_name", "id_number", "member_no")
CR_BO_POSTING_GROUP_LOOKUP_COLUMNS = ("code", "description")
CR_BOSA_STANDING_LINES_LOOKUP_COLUMNS = ("no", "destination_transaction_type", "destination_client_code", "destination_client_name", "description", "activity_code", "branch_code", "loan_no", "loan_product", "fosa_account")
CR_BUSINESS_TYPES_LOOKUP_COLUMNS = ("code", "description")
CR_CHECKOFF_ADVICE_LOOKUP_COLUMNS = ("no", "checkoff_no", "captured_by", "remarks", "employer_code", "employer_name", "posted_by", "created_by", "modified_by", "reopened_by", "payroll_group", "bank_code", "bank_name")
CR_CHECKOFF_ADVICE_DETAILS_LOOKUP_COLUMNS = ("no", "payroll_number", "client_code", "client_name", "transaction_type", "deduction_code", "description", "loan_number", "loan_product", "employer_code", "id_number", "account_type", "fosa_account", "fosa_account_no", "reference")
CR_CHECKOFF_ADVICE_IMPORTS_LOOKUP_COLUMNS = ("no", "memb_no")
CR_DIVIDEND_WITHDRAWAL_CHARGES_LOOKUP_COLUMNS = ("lower_limit", "upper_limit", "charge")
CR_DIVIDENDS_MANUAL_APPRAISAL_LOOKUP_COLUMNS = ("member_no", "member_name")
CR_EMPLOYER_PAYROLL_GROUPS_LOOKUP_COLUMNS = ("document_no", "employer_code", "employer_name")
CR_EMPLOYERS_LOOKUP_COLUMNS = ("code", "description", "associated_customer_no", "global_customer_no")
CR_EWALLET_TRANSFER_CHARGES_LOOKUP_COLUMNS = ("band", "lower_limit", "upper_limit", "charge")
CR_FIXED_DEPOSITS_LOOKUP_COLUMNS = ("no", "member_number", "member_name", "id_number", "mobile_number", "fixed_deposit_type", "fixed_deposit_certificate_no", "captured_by")
CR_FO_INTEREST_HEADER_LOOKUP_COLUMNS = ("no", "captured_by", "posted_by", "calculation_type", "remarks")
CR_FO_INTEREST_LINES_LOOKUP_COLUMNS = ("no", "member_no", "member_name", "fo_account_no", "mobile_number")
CR_FOSA_ACCRUAL_HEADER_LOOKUP_COLUMNS = ("no", "captured_by", "posted_by", "accrual_type", "bo_group", "employer_code", "employer_description", "reversed_by")
CR_FOSA_ACCRUAL_LINE_LOOKUP_COLUMNS = ("no", "client_code", "client_name", "loan_number", "loan_product", "gl_account", "payroll_number", "accrual_type", "action_type", "fosa_account_no")
CR_FOSA_STANDING_LINES_LOOKUP_COLUMNS = ("no", "account_type", "destination_client_code", "destination_client_name", "description")
CR_FOSA_TRANS_CHARGES_LOOKUP_COLUMNS = ("charge_name", "acc_no", "trans_id")
CR_CHECKOFF_ADVICE_LINE_LOOKUP_COLUMNS = (
    "no", "payroll_number", "client_code", "client_name", "transaction_type",
    "deduction_code", "description", "loan_number", "loan_product", "employer_code",
    "id_number", "account_type", "fosa_account", "fosa_account_no", "reference", "comments",
)

CR_CHECKOFF_ALLOCATIONS_LOOKUP_COLUMNS = (
    "no", "advice_no", "deduction_code", "transaction_type", "receipt_category",
    "gl_account", "loan_no", "client_code", "client_name", "global_dimension_code1",
    "global_dimension_code2", "remarks", "loan_product", "former_transaction_type",
    "fosa_account", "fosa_account_no",
)

CR_CHECKOFF_DEFAULTERS_LOOKUP_COLUMNS = (
    "document_no", "member_no", "member_name", "payroll_no", "checkoff_no",
    "employer_code", "employer_name", "account_no", "account_name", "posting_bank",
    "user_id", "user_name",
)

CR_CHECKOFF_DEFAULTERS_HEADER_LOOKUP_COLUMNS = (
    "no", "checkoff_no", "employer_code", "employer_name", "account_no",
    "account_name", "posting_bank", "user_id", "user_name",
)

CR_CHECKOFF_DEFAULTERS_SIMUNYE_LOOKUP_COLUMNS = (
    "member_number", "payroll_number",
)

CR_CHECKOFF_HEADER_LOOKUP_COLUMNS = (
    "no", "advice_no", "reversal_no", "captured_by", "remarks", "gslno",
    "account_type", "account_no", "account_name", "document_no",
    "global_dimension_code1", "global_dimension_code2", "employer_code", "employer_name",
    "checkoff_type", "checkoff_account", "posted_by", "reopened_by", "created_by",
    "modified_by", "loan_product",
)

CR_CHECKOFF_LINE_LOOKUP_COLUMNS = (
    "no", "advice_no", "payroll_number", "client_code", "client_name",
    "transaction_type", "loan_product_code", "saving_product_code", "description",
    "loan_number", "employer_code", "id_number", "account_type", "fosa_account",
    "fosa_account_no", "reference", "lda",
)

CR_CHECKOFF_STATISTICS_LOOKUP_COLUMNS = (
    "no", "client_code", "transaction_type", "loan_no", "loan_product",
    "fosa_account", "fosa_account_no",
)

CR_CHECKOFF_SUMMARY_LOOKUP_COLUMNS = (
    "no", "payroll_number", "client_code", "client_name", "transaction_type",
    "deduction_code", "description", "loan_number", "loan_product", "employer_code",
    "id_number", "account_type", "fosa_account", "fosa_account_no", "reference",
)

MEMBER_FIELD_GROUPS = {
    "identifiers": ("id", "member_number", "bo_account_no", "account_name", "cert_no"),
    "personalInformation": (
        "first_name", "middle_name", "last_name", "full_name", "gender", "date_of_birth", "marital_status",
    ),
    "contactDetails": ("mobile_number", "secondary_mobile_number", "email_address", "address"),
    "identification": ("id_number", "passport_number", "kra_pin", "document_no"),
    "membership": ("member_class", "membership_status", "membership_type", "registration_date", "approval_status"),
    "financials": ("monthly_savings", "total_deposits", "shares", "share_capital", "fo_available_balance", "total_outstanding_loan"),
    "loanExposure": ("total_active_loans", "guaranteed_loan_balances", "total_guaranteed_due", "max_mobi_loan"),
    "employment": ("employer_code", "department_code", "occupation", "payroll_number", "member_basic_salary"),
    "banking": ("bank_name", "bank_account_no", "bank_branch", "swift_code"),
    "branch": ("branch_code", "associated_branch", "company_id"),
    "referral": ("referee_member_no", "referee_name", "referee_mobile_number"),
    "balances": ("deposit_contribution_balance", "share_capital_balance", "benevolent_fund_balance"),
    "mobileControls": ("can_use_mobile_app", "can_take_mobile_loan", "has_set_security_questions"),
    "statusFlags": ("is_defaulter", "is_deceased", "is_group", "is_junior_member", "blacklistmemb", "stopped"),
    "audit": ("captured_by", "capture_date_time", "processed_by", "processed_date_time"),
}

LOAN_FIELD_GROUPS = {
    "identifiers": ("id", "loan_number", "application_no"),
    "member": ("member_number", "full_name", "id_number", "mobile_number"),
    "employment": ("employer_code", "payroll_number"),
    "loanDetails": ("loan_product", "loan_purpose", "interest_rate", "installments", "loan_category"),
    "applicationAndApproval": ("applied_amount", "approved_amount", "system_recommended_amount", "approval_status"),
    "disbursement": ("gross_disbursed_amount", "net_disbursed_amount", "amount_disbursed", "disbursement_date", "mode_of_disbursement"),
    "guarantorsAndCollateral": ("total_guarantors", "total_guaranteed_amount", "amount_guaranteed", "total_collateral_amount"),
    "repayment": ("principle_repayment", "total_monthly_repayment", "repayment_frequency", "repayment_debut_date"),
    "outstandingBalances": ("loan_balance", "outstanding_loan", "outstanding_interest", "outstanding_penalty", "outstanding_charges"),
    "arrearsAndPenalties": ("amount_in_arrears", "months_in_arrears", "days_in_arrears", "penalty_charged", "penalty_paid"),
    "interestTracking": ("interest_due", "interest_paid", "total_scheduled_interest", "last_interest_paid"),
    "qualification": ("max_qualification_by_salary", "max_qualification_by_deposits", "max_qualification_by_guarantors", "max_qualification_by_collateral"),
    "salaryAndAffordability": ("gross_salary", "net_pay", "statutory_deductions", "net_available_amount"),
    "statusAndProcessing": ("loan_status", "posted", "appraised", "cleared", "fully_disbursed", "reversed"),
    "audit": ("created_by", "approved_by", "disbursed_by", "reversed_by"),
    "banking": ("bank_name", "bank_account_no", "bank_branch", "swift_code"),
    "importantDates": ("application_date", "approval_date", "disbursement_date", "expected_end_date", "last_payment_date"),
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _compact_record(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items() if value not in (None, "")}


def _group_fields(row: dict[str, Any], groups: dict[str, tuple[str, ...]]) -> dict[str, dict[str, Any]]:
    return {
        group_name: {field: _json_value(row[field]) for field in fields if field in row and row[field] not in (None, "")}
        for group_name, fields in groups.items()
    }


def _table_columns(db: Session, table_name: str) -> set[str]:
    bind = db.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _table_metadata(columns: set[str], lookup_columns: tuple[str, ...]) -> dict[str, Any]:
    return {
        "columnCount": len(columns),
        "searchableColumns": [column for column in lookup_columns if column in columns],
    }


def _cast_type(db: Session) -> str:
    return "CHAR" if db.get_bind().dialect.name in {"mysql", "mariadb"} else "TEXT"


def _where_clause(db: Session, columns: set[str], candidates: tuple[str, ...], query: str) -> tuple[str, dict[str, str]]:
    searchable_columns = [column for column in candidates if column in columns]
    if not searchable_columns:
        return "1 = 0", {}

    terms = [query.strip()]
    terms.extend(part.strip() for part in query.replace(",", " ").split())
    unique_terms = []
    for term in terms:
        if len(term) >= 3 and term.lower() not in {item.lower() for item in unique_terms}:
            unique_terms.append(term)

    params: dict[str, str] = {}
    conditions: list[str] = []
    cast_type = _cast_type(db)
    for term_index, term in enumerate(unique_terms[:6]):
        exact_param = f"exact_{term_index}"
        like_param = f"like_{term_index}"
        params[exact_param] = term
        params[like_param] = f"%{term}%"
        for column in searchable_columns:
            quoted = f"`{column}`"
            conditions.append(f"CAST({quoted} AS {cast_type}) = :{exact_param}")
            conditions.append(f"CAST({quoted} AS {cast_type}) LIKE :{like_param}")

    return " OR ".join(conditions), params


def _fetch_one(db: Session, table_name: str, columns: set[str], where_sql: str, params: dict[str, str]) -> dict[str, Any] | None:
    result = db.execute(text(f"SELECT * FROM `{table_name}` WHERE {where_sql} LIMIT 1"), params).mappings().first()
    return dict(result) if result else None


def _fetch_loan_by_query(db: Session, query: str) -> dict[str, Any] | None:
    columns = _table_columns(db, LOAN_TABLE)
    if not columns:
        return None
    where_sql, params = _where_clause(db, columns, LOAN_LOOKUP_COLUMNS, query)
    return _fetch_one(db, LOAN_TABLE, columns, where_sql, params)


def _fetch_member_for_loan(db: Session, member_columns: set[str], loan: dict[str, Any]) -> dict[str, Any] | None:
    lookup_values = [loan.get("member_number"), loan.get("id_number"), loan.get("mobile_number")]
    predicates: list[str] = []
    params: dict[str, str] = {}
    cast_type = _cast_type(db)
    for index, value in enumerate(value for value in lookup_values if value not in (None, "")):
        param = f"loan_value_{index}"
        params[param] = str(value)
        for column in ("member_number", "id_number", "mobile_number"):
            if column in member_columns:
                predicates.append(f"CAST(`{column}` AS {cast_type}) = :{param}")
    if not predicates:
        return None
    return _fetch_one(db, MEMBER_TABLE, member_columns, " OR ".join(predicates), params)


def _fetch_loans(db: Session, member: dict[str, Any], query: str) -> list[dict[str, Any]]:
    columns = _table_columns(db, LOAN_TABLE)
    if not columns:
        return []
    lookup_values = [member.get("member_number"), member.get("id_number"), member.get("mobile_number"), member.get("bo_account_no"), query]
    predicates: list[str] = []
    params: dict[str, str] = {}
    cast_type = _cast_type(db)
    for index, value in enumerate(value for value in lookup_values if value not in (None, "")):
        param = f"value_{index}"
        params[param] = str(value)
        query_columns = LOAN_LOOKUP_COLUMNS if str(value) == query else ("member_number", "id_number", "mobile_number", "bo_account_no")
        for column in query_columns:
            if column in columns:
                predicates.append(f"CAST(`{column}` AS {cast_type}) = :{param}")
    if not predicates:
        return []
    order_column = next((column for column in ("disbursement_date", "application_date", "loan_number", "id") if column in columns), None)
    order_sql = f" ORDER BY `{order_column}` DESC" if order_column else ""
    rows = db.execute(text(f"SELECT * FROM `{LOAN_TABLE}` WHERE {' OR '.join(predicates)}{order_sql} LIMIT 100"), params).mappings().all()
    return [dict(row) for row in rows]


# Generic helper to create a table query function


def _make_table_query(table_name: str, lookup_cols: tuple[str, ...], order_col: str = "id"):

    def query_fn(db: Session, query: str) -> dict[str, Any]:
        clean_query = query.strip()
        columns = _table_columns(db, table_name)
        if not columns:
            return {"table": table_name, "error": f"Table {table_name} was not found in the configured database", "records": [], "count": 0}
        
        # If query is empty, "all", or too short, return all records (no WHERE clause)
        list_all = not clean_query or clean_query.lower() in ("all", "*", "list", "all records")
        if list_all:
            order_sql = f" ORDER BY `{order_col}` DESC" if order_col in columns else ""
            rows = db.execute(text(f"SELECT * FROM `{table_name}`{order_sql} LIMIT 100"), params={}).mappings().all()
            records = [dict(row) for row in rows]
            return {"table": table_name, "tableMetadata": _table_metadata(columns, lookup_cols), "query": clean_query or "all", "count": len(records), "records": records}
        
        if len(clean_query) < 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter at least 3 characters to search")
        where_sql, params = _where_clause(db, columns, lookup_cols, clean_query)
        order_sql = f" ORDER BY `{order_col}` DESC" if order_col in columns else ""
        rows = db.execute(text(f"SELECT * FROM `{table_name}` WHERE {where_sql}{order_sql} LIMIT 50"), params).mappings().all()
        records = [dict(row) for row in rows]
        return {"table": table_name, "tableMetadata": _table_metadata(columns, lookup_cols), "query": clean_query, "count": len(records), "records": records}

    return query_fn


# Generated table query functions


get_alazar_records = _make_table_query(ALAZAR_TABLE, ALAZAR_LOOKUP_COLUMNS)
get_item_tracking_lines = _make_table_query(ITEM_TRACKING_TABLE, ITEM_TRACKING_LOOKUP_COLUMNS)
get_loan_disbursement_dates = _make_table_query(LOAN_DISBURSEMENT_TABLE, LOAN_DISBURSEMENT_LOOKUP_COLUMNS, order_col="date")
get_payslip_details = _make_table_query(PAYSLIP_DETAILS_TABLE, PAYSLIP_DETAILS_LOOKUP_COLUMNS)
get_stock_taking_header = _make_table_query(STOCK_TAKING_HEADER_TABLE, STOCK_TAKING_HEADER_LOOKUP_COLUMNS, order_col="Last_Modified_Date")
get_address_update = _make_table_query(ADDRESS_UPDATE_TABLE, ADDRESS_UPDATE_LOOKUP_COLUMNS)
get_advance_loans = _make_table_query(ADVANCE_LOANS_TABLE, ADVANCE_LOANS_LOOKUP_COLUMNS, order_col="created_at")
get_ahadi_paye = _make_table_query(AHADI_PAYE_TABLE, AHADI_PAYE_LOOKUP_COLUMNS)
get_airtel_discounts = _make_table_query(AIRTEL_DISCOUNTS_TABLE, AIRTEL_DISCOUNTS_LOOKUP_COLUMNS, order_col="discount_id")
get_airtime_merchant_logs = _make_table_query(AIRTIME_MERCHANT_LOGS_TABLE, AIRTIME_MERCHANT_LOGS_LOOKUP_COLUMNS, order_col="transaction_time")
get_all_nationsdetails = _make_table_query(ALL_NATIONSDETAILS_TABLE, ALL_NATIONSDETAILS_LOOKUP_COLUMNS)
get_assessment_books = _make_table_query(ASSESSMENT_BOOKS_TABLE, ASSESSMENT_BOOKS_LOOKUP_COLUMNS, order_col="uploaded_at")
get_attendance_lines = _make_table_query(ATTENDANCE_LINES_TABLE, ATTENDANCE_LINES_LOOKUP_COLUMNS)
get_barter_transactions = _make_table_query(BARTER_TRANSACTIONS_TABLE, BARTER_TRANSACTIONS_LOOKUP_COLUMNS, order_col="date_modified")
get_biodata_rainforest = _make_table_query(BIODATA_RAINFOREST_TABLE, BIODATA_RAINFOREST_LOOKUP_COLUMNS)
get_book_assignments = _make_table_query(BOOK_ASSIGNMENTS_TABLE, BOOK_ASSIGNMENTS_LOOKUP_COLUMNS, order_col="assigned_at")
get_books = _make_table_query(BOOKS_TABLE, BOOKS_LOOKUP_COLUMNS)
get_braun = _make_table_query(BRAUN_TABLE, BRAUN_LOOKUP_COLUMNS)
get_bu_commitees = _make_table_query(BU_COMMITEES_TABLE, BU_COMMITEES_LOOKUP_COLUMNS)
get_bu_requisition_header = _make_table_query(BU_REQUISITION_HEADER_TABLE, BU_REQUISITION_HEADER_LOOKUP_COLUMNS, order_col="document_date")
get_bu_requisition_lines = _make_table_query(BU_REQUISITION_LINES_TABLE, BU_REQUISITION_LINES_LOOKUP_COLUMNS)
get_budget = _make_table_query(BUDGET_TABLE, BUDGET_LOOKUP_COLUMNS, order_col="entry_date")
get_budget_allocations = _make_table_query(BUDGET_ALLOCATIONS_TABLE, BUDGET_ALLOCATIONS_LOOKUP_COLUMNS)
get_budget_line = _make_table_query(BUDGET_LINE_TABLE, BUDGET_LINE_LOOKUP_COLUMNS)
get_calender_of_events = _make_table_query(CALENDER_OF_EVENTS_TABLE, CALENDER_OF_EVENTS_LOOKUP_COLUMNS, order_col="event_date")
get_cash_flow_forecast = _make_table_query(CASH_FLOW_FORECAST_TABLE, CASH_FLOW_FORECAST_LOOKUP_COLUMNS, order_col="entry_date")
get_cash_forecast_allocations = _make_table_query(CASH_FORECAST_ALLOCATIONS_TABLE, CASH_FORECAST_ALLOCATIONS_LOOKUP_COLUMNS)
get_cash_forecast_line = _make_table_query(CASH_FORECAST_LINE_TABLE, CASH_FORECAST_LINE_LOOKUP_COLUMNS)
get_cash_receipts = _make_table_query(CASH_RECEIPTS_TABLE, CASH_RECEIPTS_LOOKUP_COLUMNS)
get_cat_questions = _make_table_query(CAT_QUESTIONS_TABLE, CAT_QUESTIONS_LOOKUP_COLUMNS, order_col="question_no")
get_category_types = _make_table_query(CATEGORY_TYPES_TABLE, CATEGORY_TYPES_LOOKUP_COLUMNS)
get_cbk_transfers = _make_table_query(CBK_TRANSFERS_TABLE, CBK_TRANSFERS_LOOKUP_COLUMNS, order_col="date_modified")
get_cbo_members = _make_table_query(CBO_MEMBERS_TABLE, CBO_MEMBERS_LOOKUP_COLUMNS)
get_cft_income_accrual_lines = _make_table_query(CFT_INCOME_ACCRUAL_LINES_TABLE, CFT_INCOME_ACCRUAL_LINES_LOOKUP_COLUMNS)
get_cft_income_accruals = _make_table_query(CFT_INCOME_ACCRUALS_TABLE, CFT_INCOME_ACCRUALS_LOOKUP_COLUMNS, order_col="entry_date")
get_ci_sessions = _make_table_query(CI_SESSIONS_TABLE, CI_SESSIONS_LOOKUP_COLUMNS, order_col="last_activity")
get_closing_interest_siginon = _make_table_query(CLOSING_INTEREST_SIGINON_TABLE, CLOSING_INTEREST_SIGINON_LOOKUP_COLUMNS)
get_co_imprest_requisition_lines = _make_table_query(CO_IMPREST_REQUISITION_LINES_TABLE, CO_IMPREST_REQUISITION_LINES_LOOKUP_COLUMNS)
get_co_imprest_requisitions = _make_table_query(CO_IMPREST_REQUISITIONS_TABLE, CO_IMPREST_REQUISITIONS_LOOKUP_COLUMNS, order_col="requisition_date")
get_co_imprest_surrender = _make_table_query(CO_IMPREST_SURRENDER_TABLE, CO_IMPREST_SURRENDER_LOOKUP_COLUMNS, order_col="requisition_date")
get_co_imprest_surrender_lines = _make_table_query(CO_IMPREST_SURRENDER_LINES_TABLE, CO_IMPREST_SURRENDER_LINES_LOOKUP_COLUMNS)
get_co_imprest_surrender_linesold = _make_table_query(CO_IMPREST_SURRENDER_LINESOLD_TABLE, CO_IMPREST_SURRENDER_LINESOLD_LOOKUP_COLUMNS)
get_co_imprest_surrenderold = _make_table_query(CO_IMPREST_SURRENDEROLD_TABLE, CO_IMPREST_SURRENDEROLD_LOOKUP_COLUMNS, order_col="requisition_date")
get_coa_groups = _make_table_query(COA_GROUPS_TABLE, COA_GROUPS_LOOKUP_COLUMNS)
get_coa_sub_groups = _make_table_query(COA_SUB_GROUPS_TABLE, COA_SUB_GROUPS_LOOKUP_COLUMNS)
get_coop_lines = _make_table_query(COOP_LINES_TABLE, COOP_LINES_LOOKUP_COLUMNS)
get_correction_deposits = _make_table_query(CORRECTION_DEPOSITS_TABLE, CORRECTION_DEPOSITS_LOOKUP_COLUMNS)
get_cr_loan_amount_bands = _make_table_query(CR_LOAN_AMOUNT_BANDS_TABLE, CR_LOAN_AMOUNT_BANDS_LOOKUP_COLUMNS)
get_cr_account_types = _make_table_query(CR_ACCOUNT_TYPES_TABLE, CR_ACCOUNT_TYPES_LOOKUP_COLUMNS)
get_cr_accrual_header = _make_table_query(CR_ACCRUAL_HEADER_TABLE, CR_ACCRUAL_HEADER_LOOKUP_COLUMNS, order_col="entry_date")
get_cr_accrual_line = _make_table_query(CR_ACCRUAL_LINE_TABLE, CR_ACCRUAL_LINE_LOOKUP_COLUMNS)
get_cr_arrears_offset = _make_table_query(CR_ARREARS_OFFSET_TABLE, CR_ARREARS_OFFSET_LOOKUP_COLUMNS)
get_cr_banking_agents = _make_table_query(CR_BANKING_AGENTS_TABLE, CR_BANKING_AGENTS_LOOKUP_COLUMNS, order_col="application_date")
get_cr_bo_accounts_nos = _make_table_query(CR_BO_ACCOUNTS_NOS_TABLE, CR_BO_ACCOUNTS_NOS_LOOKUP_COLUMNS)
get_cr_bo_applications = _make_table_query(CR_BO_APPLICATIONS_TABLE, CR_BO_APPLICATIONS_LOOKUP_COLUMNS, order_col="application_date")
get_cr_bo_applications_old = _make_table_query(CR_BO_APPLICATIONS_OLD_TABLE, CR_BO_APPLICATIONS_OLD_LOOKUP_COLUMNS, order_col="application_date")
get_cr_bo_charges = _make_table_query(CR_BO_CHARGES_TABLE, CR_BO_CHARGES_LOOKUP_COLUMNS, order_col="date")
get_cr_bo_departments = _make_table_query(CR_BO_DEPARTMENTS_TABLE, CR_BO_DEPARTMENTS_LOOKUP_COLUMNS)
get_cr_bo_deposit_classification = _make_table_query(CR_BO_DEPOSIT_CLASSIFICATION_TABLE, CR_BO_DEPOSIT_CLASSIFICATION_LOOKUP_COLUMNS, order_col="date")
get_cr_bo_general_setup = _make_table_query(CR_BO_GENERAL_SETUP_TABLE, CR_BO_GENERAL_SETUP_LOOKUP_COLUMNS)
get_cr_bo_insider_borrowers = _make_table_query(CR_BO_INSIDER_BORROWERS_TABLE, CR_BO_INSIDER_BORROWERS_LOOKUP_COLUMNS, order_col="last_updated")
get_cr_bo_ledger_entry = _make_table_query(CR_BO_LEDGER_ENTRY_TABLE, CR_BO_LEDGER_ENTRY_LOOKUP_COLUMNS, order_col="posting_date")
get_cr_bo_mobile_applications = _make_table_query(CR_BO_MOBILE_APPLICATIONS_TABLE, CR_BO_MOBILE_APPLICATIONS_LOOKUP_COLUMNS, order_col="application_date")
get_cr_bo_posting_group = _make_table_query(CR_BO_POSTING_GROUP_TABLE, CR_BO_POSTING_GROUP_LOOKUP_COLUMNS)
get_cr_bosa_standing_lines = _make_table_query(CR_BOSA_STANDING_LINES_TABLE, CR_BOSA_STANDING_LINES_LOOKUP_COLUMNS)
get_cr_business_types = _make_table_query(CR_BUSINESS_TYPES_TABLE, CR_BUSINESS_TYPES_LOOKUP_COLUMNS)
get_cr_checkoff_advice = _make_table_query(CR_CHECKOFF_ADVICE_TABLE, CR_CHECKOFF_ADVICE_LOOKUP_COLUMNS, order_col="entry_date")
get_cr_checkoff_advice_details = _make_table_query(CR_CHECKOFF_ADVICE_DETAILS_TABLE, CR_CHECKOFF_ADVICE_DETAILS_LOOKUP_COLUMNS)
get_cr_checkoff_advice_imports = _make_table_query(CR_CHECKOFF_ADVICE_IMPORTS_TABLE, CR_CHECKOFF_ADVICE_IMPORTS_LOOKUP_COLUMNS)

# --- New checkoff query functions ---
get_cr_checkoff_advice_line = _make_table_query(CR_CHECKOFF_ADVICE_LINE_TABLE, CR_CHECKOFF_ADVICE_LINE_LOOKUP_COLUMNS)
get_cr_checkoff_allocations = _make_table_query(CR_CHECKOFF_ALLOCATIONS_TABLE, CR_CHECKOFF_ALLOCATIONS_LOOKUP_COLUMNS)
get_cr_checkoff_defaulters = _make_table_query(CR_CHECKOFF_DEFAULTERS_TABLE, CR_CHECKOFF_DEFAULTERS_LOOKUP_COLUMNS, order_col="posting_date")
get_cr_checkoff_defaulters_header = _make_table_query(CR_CHECKOFF_DEFAULTERS_HEADER_TABLE, CR_CHECKOFF_DEFAULTERS_HEADER_LOOKUP_COLUMNS, order_col="posting_date")
get_cr_checkoff_defaulters_simunye = _make_table_query(CR_CHECKOFF_DEFAULTERS_SIMUNYE_TABLE, CR_CHECKOFF_DEFAULTERS_SIMUNYE_LOOKUP_COLUMNS)
get_cr_checkoff_header = _make_table_query(CR_CHECKOFF_HEADER_TABLE, CR_CHECKOFF_HEADER_LOOKUP_COLUMNS, order_col="entry_date")
get_cr_checkoff_line = _make_table_query(CR_CHECKOFF_LINE_TABLE, CR_CHECKOFF_LINE_LOOKUP_COLUMNS)
get_cr_checkoff_statistics = _make_table_query(CR_CHECKOFF_STATISTICS_TABLE, CR_CHECKOFF_STATISTICS_LOOKUP_COLUMNS)
get_cr_checkoff_summary = _make_table_query(CR_CHECKOFF_SUMMARY_TABLE, CR_CHECKOFF_SUMMARY_LOOKUP_COLUMNS)

get_cr_dividend_withdrawal_charges = _make_table_query(CR_DIVIDEND_WITHDRAWAL_CHARGES_TABLE, CR_DIVIDEND_WITHDRAWAL_CHARGES_LOOKUP_COLUMNS)
get_cr_dividends_manual_appraisal = _make_table_query(CR_DIVIDENDS_MANUAL_APPRAISAL_TABLE, CR_DIVIDENDS_MANUAL_APPRAISAL_LOOKUP_COLUMNS)
get_cr_employer_payroll_groups = _make_table_query(CR_EMPLOYER_PAYROLL_GROUPS_TABLE, CR_EMPLOYER_PAYROLL_GROUPS_LOOKUP_COLUMNS)
get_cr_employers = _make_table_query(CR_EMPLOYERS_TABLE, CR_EMPLOYERS_LOOKUP_COLUMNS)
get_cr_ewallet_transfer_charges = _make_table_query(CR_EWALLET_TRANSFER_CHARGES_TABLE, CR_EWALLET_TRANSFER_CHARGES_LOOKUP_COLUMNS)
get_cr_fixed_deposits = _make_table_query(CR_FIXED_DEPOSITS_TABLE, CR_FIXED_DEPOSITS_LOOKUP_COLUMNS, order_col="start_date")
get_cr_fo_interest_header = _make_table_query(CR_FO_INTEREST_HEADER_TABLE, CR_FO_INTEREST_HEADER_LOOKUP_COLUMNS, order_col="entry_date")
get_cr_fo_interest_lines = _make_table_query(CR_FO_INTEREST_LINES_TABLE, CR_FO_INTEREST_LINES_LOOKUP_COLUMNS)
get_cr_fosa_accrual_header = _make_table_query(CR_FOSA_ACCRUAL_HEADER_TABLE, CR_FOSA_ACCRUAL_HEADER_LOOKUP_COLUMNS, order_col="entry_date")
get_cr_fosa_accrual_line = _make_table_query(CR_FOSA_ACCRUAL_LINE_TABLE, CR_FOSA_ACCRUAL_LINE_LOOKUP_COLUMNS)
get_cr_fosa_standing_lines = _make_table_query(CR_FOSA_STANDING_LINES_TABLE, CR_FOSA_STANDING_LINES_LOOKUP_COLUMNS)
get_cr_fosa_trans_charges = _make_table_query(CR_FOSA_TRANS_CHARGES_TABLE, CR_FOSA_TRANS_CHARGES_LOOKUP_COLUMNS)


def get_member_intelligence(db: Session, query: str) -> dict[str, Any]:
    clean_query = query.strip()
    if len(clean_query) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter at least 3 characters to search")

    member_columns = _table_columns(db, MEMBER_TABLE)
    loan_columns = _table_columns(db, LOAN_TABLE)
    if not member_columns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Table {MEMBER_TABLE} was not found in the configured database")

    where_sql, params = _where_clause(db, member_columns, MEMBER_LOOKUP_COLUMNS, clean_query)
    member = _fetch_one(db, MEMBER_TABLE, member_columns, where_sql, params)
    match_source = "member"
    matched_loan = None
    if not member:
        matched_loan = _fetch_loan_by_query(db, clean_query)
        if matched_loan:
            member = _fetch_member_for_loan(db, member_columns, matched_loan) or {}
            match_source = "loan"
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No member or loan found in cr_bo_accounts/cr_loans")

    loans = _fetch_loans(db, member, clean_query)
    matched_loan_key = (matched_loan.get("id"), matched_loan.get("loan_number"), matched_loan.get("application_no")) if matched_loan else None
    if matched_loan and not any((loan.get("id"), loan.get("loan_number"), loan.get("application_no")) == matched_loan_key for loan in loans):
        loans.insert(0, matched_loan)

    return {
        "sourceTables": {"member": MEMBER_TABLE, "loans": LOAN_TABLE},
        "tableMetadata": {"member": _table_metadata(member_columns, MEMBER_LOOKUP_COLUMNS), "loans": _table_metadata(loan_columns, LOAN_LOOKUP_COLUMNS)},
        "query": clean_query,
        "matchSource": match_source,
        "member": {"summary": _group_fields(member, MEMBER_FIELD_GROUPS), "allFields": _compact_record(member)},
        "loans": [{"summary": _group_fields(loan, LOAN_FIELD_GROUPS), "allFields": _compact_record(loan)} for loan in loans],
        "loanCount": len(loans),
    }
import os
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import SESSION_IDLE_MINUTES
from app.database import get_ai_read_only_db
from app.security import bearer_scheme, hash_token, user_from_env_admin_token
from app.models.models import AuthToken, Member, Loan, Transaction, PortfolioSnapshot, User
from app.services.member_intelligence import (
    get_member_intelligence,
    get_alazar_records, get_item_tracking_lines, get_loan_disbursement_dates,
    get_payslip_details, get_stock_taking_header, get_address_update,
    get_advance_loans, get_ahadi_paye, get_airtel_discounts,
    get_airtime_merchant_logs, get_all_nationsdetails, get_assessment_books,
    get_attendance_lines, get_barter_transactions, get_biodata_rainforest,
    get_book_assignments, get_books, get_braun,
    get_bu_commitees, get_bu_requisition_header, get_bu_requisition_lines,
    get_budget, get_budget_allocations, get_budget_line,
    get_calender_of_events, get_cash_flow_forecast, get_cash_forecast_allocations,
    get_cash_forecast_line, get_cash_receipts, get_cat_questions,
    get_category_types, get_cbk_transfers, get_cbo_members,
    get_cft_income_accrual_lines, get_cft_income_accruals, get_ci_sessions,
    get_closing_interest_siginon, get_co_imprest_requisition_lines,
    get_co_imprest_requisitions, get_co_imprest_surrender,
    get_co_imprest_surrender_lines, get_co_imprest_surrender_linesold,
    get_co_imprest_surrenderold, get_coa_groups, get_coa_sub_groups,
    get_coop_lines, get_correction_deposits, get_cr_loan_amount_bands,
    get_cr_account_types,
    get_cr_accrual_header, get_cr_accrual_line, get_cr_arrears_offset,
    get_cr_banking_agents, get_cr_bo_accounts_nos, get_cr_bo_applications,
    get_cr_bo_applications_old, get_cr_bo_charges, get_cr_bo_departments,
    get_cr_bo_deposit_classification, get_cr_bo_general_setup,
    get_cr_bo_insider_borrowers, get_cr_bo_ledger_entry,
    get_cr_bo_mobile_applications, get_cr_bo_posting_group,
    get_cr_bosa_standing_lines,
    get_cr_business_types, get_cr_checkoff_advice, get_cr_checkoff_advice_details,
    get_cr_checkoff_advice_imports,
    get_cr_checkoff_advice_line,
    get_cr_checkoff_allocations,
    get_cr_checkoff_defaulters,
    get_cr_checkoff_defaulters_header,
    get_cr_checkoff_defaulters_simunye,
    get_cr_checkoff_header,
    get_cr_checkoff_line,
    get_cr_checkoff_statistics,
    get_cr_checkoff_summary,
    get_cr_dividend_withdrawal_charges,
    get_cr_dividends_manual_appraisal,
    get_cr_employer_payroll_groups,
    get_cr_employers,
    get_cr_ewallet_transfer_charges,
    get_cr_fixed_deposits,
    get_cr_fo_interest_header,
    get_cr_fo_interest_lines,
    get_cr_fosa_accrual_header,
    get_cr_fosa_accrual_line,
    get_cr_fosa_standing_lines,
    get_cr_fosa_trans_charges,
)

logger = logging.getLogger("umojafunds.ai_query")

router = APIRouter(prefix="/api/ai-query", tags=["ai-query"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# Tool / function declarations – Gemini decides which to call based on the
# conversation.  Each tool maps directly to a SQLALchemy query against the
# internal models OR the external MySQL member-intelligence service.

TOOL_DEFINITIONS = [
    {
        "name": "query_members",
        "description": "Query SACCO member records from the internal database. Use this to get member details, filter by status, or search by name/ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional search term to match against member name or ID.",
                },
                "status": {
                    "type": "string",
                    "enum": ["Active", "Inactive", "Suspended"],
                    "description": "Filter by membership status.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (default 50, max 200).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "query_loans",
        "description": "Query loan records from the internal database. Filter by status, member, or type.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["Active", "Overdue", "Completed", "Pending"],
                    "description": "Filter by loan status.",
                },
                "member_id": {
                    "type": "string",
                    "description": "Filter by member ID.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records (default 50, max 200).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "query_transactions",
        "description": "Query transaction records from the internal database. Filter by type, member, or category.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["Credit", "Debit"],
                    "description": "Filter by transaction type.",
                },
                "member_id": {
                    "type": "string",
                    "description": "Filter by member ID.",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by transaction category (e.g. 'Savings Deposit', 'Loan Repayment', 'Withdrawal').",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records (default 50, max 200).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_member_intelligence",
        "description": "Look up a member in the EXTERNAL MySQL database tables (cr_bo_accounts, cr_loans) using member number, account number, phone, ID number, name, or loan number. Returns comprehensive member and loan data from those tables.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number, account number, phone number, ID number, name, or loan number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_portfolio_summary",
        "description": "Get an aggregated summary of the entire SACCO portfolio including total savings, total loans outstanding, active member count, overdue loan count and amount, and NPL ratio.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "query_alazar",
        "description": "Search records in the Alazar table (external MySQL database) by admission number (adm_no) or mobile_number. Returns matching records with id, adm_no, mobile_number, and company_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Admission number or mobile number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_item_tracking_lines",
        "description": "Search records in the Item_Tracking_lines table (external MySQL database) by stocktake code, item code, package code, location code, description, or entry type. Returns inventory tracking records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Stocktake code, item code, package code, location code, description, or entry type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_loan_disbursement_dates",
        "description": "Search records in the Loan_disbursement_dates table (external MySQL database) by loan number (Loan_no). Returns matching records with loan number, disbursement date, and company_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Loan number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_payslip_details",
        "description": "Search records in the Payslip_details table (external MySQL database) by employer code, payroll number, member name, bank name, bank account number, or ID number. Returns payslip details including basic pay, allowances, and banking info.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Employer code, payroll number, member name, bank name, bank account number, or ID number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_stock_taking_header",
        "description": "Search records in the Stock_Taking_Setup_Header table (external MySQL database) by Code, Description, Created_By, type, lead_by, Status, or dimension_code. Returns stock taking setup information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Code, description, creator name, stock taking type, lead name, status, or dimension code to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_address_update",
        "description": "Search records in the address_update table (external MySQL database) by member number (mno) or address. Returns matching address update records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number or address to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_advance_loans",
        "description": "Search records in the advance_loans table (external MySQL database) by user_id, teacher_id, name, or status. Returns advance loan applications with amounts and status.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "User ID, teacher ID, first name, middle name, last name, or status to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_ahadi_paye",
        "description": "Search records in the ahadi_paye table (external MySQL database) by staff number (staff_no). Returns paye records with staff number, amount, and company_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Staff number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_airtel_discounts",
        "description": "Search records in the airtel_discounts table (external MySQL database) by discount_id or status. Returns airtel discount records with limits and discount values.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Discount ID or status to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_airtime_merchant_logs",
        "description": "Search records in the airtime_merchant_logs table (external MySQL database) by type or loaded_by. Returns airtime merchant transaction logs.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Transaction type or loaded_by user to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_all_nationsdetails",
        "description": "Search records in the all_nationsdetails table (external MySQL database) by member_no or group_code. Returns member-group assignment records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number or group code to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_assessment_books",
        "description": "Search records in the assessment_books table (external MySQL database) by class_name, subject_name, file_name, or file_type. Returns assessment book records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Class name, subject name, file name, or file type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_attendance_lines",
        "description": "Search records in the attendance_lines table (external MySQL database) by admin_no, full_name, status, Month, or Year. Returns attendance records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Admin number, full name, status, month, or year to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_barter_transactions",
        "description": "Search records in the barter_transactions table (external MySQL database) by document number, account details, approval status, user, description, invoice, or bill number. Returns barter transaction records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, account number, account name, approval status, user, or description to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_biodata_rainforest",
        "description": "Search records in the biodata_rainforest table (external MySQL database) by member_number, ID, phone, employer_code, employer_description, email, or member_status. Returns member biodata records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number, ID number, phone, employer code, employer description, email, or member status to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_book_assignments",
        "description": "Search records in the book_assignments table (external MySQL database) by book_no, book_id, admission_no, student_name, student_class, or assigned_by. Returns book assignment records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Book number, book ID, admission number, student name, class, or assigned by to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_books",
        "description": "Search records in the books table (external MySQL database) by title, author, book_no, class, subject, status, or location. Returns library book records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Title, author, book number, class, subject, status, or location to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_braun",
        "description": "Search records in the braun table (external MySQL database) by ID number (id_no). Returns braun ID records.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "ID number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_bu_commitees",
        "description": "Search records in the bu_commitees table (external MySQL database) by committee code or name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Committee code or name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_bu_requisition_header",
        "description": "Search records in the bu_requisition_header table (external MySQL database) by requisition number, committee code, committee name, description, or venue.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Requisition number, committee code/name, description, or venue to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_bu_requisition_lines",
        "description": "Search records in the bu_requisition_lines table (external MySQL database) by requisition number, item code, or item name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Requisition number, item code, or item name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_budget",
        "description": "Search records in the budget table (external MySQL database) by budget number, account number, account name, document number, dimension codes, or checkoff account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Budget number, account number, account name, document number, dimension code, or checkoff account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_budget_allocations",
        "description": "Search records in the budget_allocations table (external MySQL database) by budget number, transaction type, receipt category, GL account, loan number, account number, account name, or FOSA account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Budget number, transaction type, receipt category, GL account, loan number, account number, account name, or FOSA account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_budget_line",
        "description": "Search records in the budget_line table (external MySQL database) by budget number, payroll number, account number, account name, transaction type, description, loan number, employer code, ID number, FOSA account, or reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Budget number, payroll number, account number, account name, transaction type, description, loan number, employer code, ID number, FOSA account, or reference to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_calender_of_events",
        "description": "Search records in the calender_of_events table (external MySQL database) by activity name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Activity name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cash_flow_forecast",
        "description": "Search records in the cash_flow_forecast table (external MySQL database) by forecast number, account number, account name, document number, dimension codes, or checkoff account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Forecast number, account number, account name, document number, dimension code, or checkoff account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cash_forecast_allocations",
        "description": "Search records in the cash_forecast_allocations table (external MySQL database) by forecast number, transaction type, receipt category, GL account, loan number, account number, account name, or FOSA account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Forecast number, transaction type, receipt category, GL account, loan number, account number, account name, or FOSA account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cash_forecast_line",
        "description": "Search records in the cash_forecast_line table (external MySQL database) by forecast number, payroll number, account number, account name, transaction type, description, loan number, employer code, ID number, FOSA account, or reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Forecast number, payroll number, account number, account name, transaction type, description, loan number, employer code, ID number, FOSA account, or reference to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cash_receipts",
        "description": "Search records in the cash_receipts table (external MySQL database) by receipt number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Receipt number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cat_questions",
        "description": "Search records in the cat_questions table (external MySQL database) by exam code, subject code, class code, teacher ID, or file number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Exam code, subject code, class code, teacher ID, or file number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_category_types",
        "description": "Search records in the category_types table (external MySQL database) by sub code, type code, or type name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Sub code, type code, or type name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cbk_transfers",
        "description": "Search records in the cbk_transfers table (external MySQL database) by document number, destination/source document number, CBK source/destination code, external document number, transaction type, or user.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, source/dest doc number, CBK code, external document number, transaction type, or user to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cbo_members",
        "description": "Search records in the cbo_members table (external MySQL database) by member number or group code.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number or group code to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cft_income_accrual_lines",
        "description": "Search records in the cft_income_accrual_lines table (external MySQL database) by accrual number, client code, client name, GL account, activity code, or branch code.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Accrual number, client code, client name, GL account, activity code, or branch code to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cft_income_accruals",
        "description": "Search records in the cft_income_accruals table (external MySQL database) by accrual number, account type, account number, account name, activity code, branch code, transaction type, captured by, or posted by.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Accrual number, account type, account number, account name, activity code, branch code, transaction type, captured by, or posted by to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_ci_sessions",
        "description": "Search records in the ci_sessions table (external MySQL database) by session ID, IP address, or status.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Session ID, IP address, or status to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_closing_interest_siginon",
        "description": "Search records in the closing_interest_siginon table (external MySQL database) by ID, loan number, or member number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "ID, loan number, or member number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_co_imprest_requisition_lines",
        "description": "Search records in the co_imprest_requisition_lines table (external MySQL database) by item code, document number, GL account, votehead code, cheque number, CBK code, account type, account number, account name, or payment type.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Item code, document number, GL account, votehead, cheque/CBK code, account details, or payment type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_co_imprest_requisitions",
        "description": "Search records in the co_imprest_requisitions table (external MySQL database) by document number, display document number, staff number, staff name, user ID, cheque number, CBK code, account numbers, customer number, client name, or payment type.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, staff details, user ID, cheque/CBK code, account numbers, customer/client name, or payment type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_co_imprest_surrender",
        "description": "Search records in the co_imprest_surrender table (external MySQL database) by document number, display document number, client ID, client name, user ID, cheque number, CBK code, account numbers, customer number, payment type, or requisition number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, client details, user ID, cheque/CBK code, account numbers, customer number, payment type, or requisition number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_co_imprest_surrender_lines",
        "description": "Search records in the co_imprest_surrender_lines table (external MySQL database) by item name, document number, GL account, votehead code, cheque number, CBK code, account type, account number, account name, or payment type.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Item name, document number, GL account, votehead, cheque/CBK code, account details, or payment type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_co_imprest_surrender_linesold",
        "description": "Search records in the co_imprest_surrender_linesold table (external MySQL database) by item code, document number, GL account, votehead code, cheque number, CBK code, or surrender document number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Item code, document number, GL account, votehead, cheque/CBK code, or surrender document number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_co_imprest_surrenderold",
        "description": "Search records in the co_imprest_surrenderold table (external MySQL database) by document number, staff number, staff name, user ID, cheque number, CBK code, account numbers, or surrender document number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, staff details, user ID, cheque/CBK code, account numbers, or surrender document number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_coa_groups",
        "description": "Search records in the coa_groups table (external MySQL database) by group code or group name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Group code or group name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_coa_sub_groups",
        "description": "Search records in the coa_sub_groups table (external MySQL database) by code, sub code, or sub group name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Code, sub code, or sub group name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_coop_lines",
        "description": "Search records in the coop_lines table (external MySQL database) by customer memo lines or event type.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Customer memo line 1, 2, 3, or event type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_correction_deposits",
        "description": "Search records in the correction_deposits table (external MySQL database) by member number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_loan_amount_bands",
        "description": "Search records in the cr_Loan_amount_bands table (external MySQL database) by band code or loan product name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Band code or loan product name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_account_types",
        "description": "Search records in the cr_account_types table (external MySQL database) by account type code.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Account type code to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_accrual_header",
        "description": "Search records in the cr_accrual_header table (external MySQL database) by accrual number, captured by, posted by, accrual type, BO group, employer code/description, or reversed by.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Accrual number, captured by, posted by, accrual type, BO group, employer code, employer description, or reversed by to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_accrual_line",
        "description": "Search records in the cr_accrual_line table (external MySQL database) by accrual number, client code, client name, loan number, loan product, GL account, payroll number, accrual type, or action type.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Accrual number, client code, client name, loan number, loan product, GL account, payroll number, accrual type, or action type to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_arrears_offset",
        "description": "Search records in the cr_arrears_offset table (external MySQL database) by loan number, topup loan number, loan to offset, client code, or loan product.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Loan number, topup loan number, loan to offset, client code, or loan product to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_banking_agents",
        "description": "Search records in the cr_banking_agents table (external MySQL database) by agent number, ID number, phone number, mobile number, first/middle/last/full name, or agency name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Agent number, ID number, phone/mobile number, name, or agency name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_accounts_nos",
        "description": "Search records in the cr_bo_accounts_nos table (external MySQL database) by member number or mobile number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number or mobile number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_applications",
        "description": "Search records in the cr_bo_applications table (external MySQL database) by application number, name, account name, ID number, passport number, member number, mobile number, email, employer code, payroll number, BO account, or referee details.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Application number, name, account name, ID/passport number, member number, mobile number, email, employer code, payroll number, BO account, or referee details to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_applications_old",
        "description": "Search records in the cr_bo_applications_old table (external MySQL database) by application number, name, ID number, member number, mobile number, email, employer code, payroll number, BO account, or referee details.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Application number, name, ID number, member number, mobile number, email, employer code, payroll number, BO account, or referee details to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_charges",
        "description": "Search records in the cr_bo_charges table (external MySQL database) by member number, document number, transaction type, or loan number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number, document number, transaction type, or loan number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_departments",
        "description": "Search records in the cr_bo_departments table (external MySQL database) by department code or description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Department code or description to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_deposit_classification",
        "description": "Search records in the cr_bo_deposit_classification table (external MySQL database) by member number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_general_setup",
        "description": "Search records in the cr_bo_general_setup table (external MySQL database) by company number series, default customer posting group, or institution founding date.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Company number series, customer posting group, or founding date to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_insider_borrowers",
        "description": "Search records in the cr_bo_insider_borrowers table (external MySQL database) by member number, name, or position.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number, name, or position to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_ledger_entry",
        "description": "Search records in the cr_bo_ledger_entry table (external MySQL database) by client code, document number, loan number, transaction type, description, user name, source code, document type, payment reference, FOSA account, or external document number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Client code, document/loan number, transaction type, description, user name, source code, document type, payment reference, FOSA account, or external document number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_mobile_applications",
        "description": "Search records in the cr_bo_mobile_applications table (external MySQL database) by mobile number, account number, full name, ID number, or member number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Mobile number, account number, full name, ID number, or member number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bo_posting_group",
        "description": "Search records in the cr_bo_posting_group table (external MySQL database) by posting group code or description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Posting group code or description to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_bosa_standing_lines",
        "description": "Search records in the cr_bosa_standing_lines table (external MySQL database) by standing order number, transaction type, client code, client name, description, activity code, branch code, loan number, loan product, or FOSA account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Standing order number, transaction type, client code/name, description, activity/branch code, loan number/product, or FOSA account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_business_types",
        "description": "Search records in the cr_business_types table (external MySQL database) by business type code or description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Business type code or description to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_advice",
        "description": "Search records in the cr_checkoff_advice table (external MySQL database) by advice number, checkoff number, captured by, remarks, employer code/name, posted by, created/modified/reopened by, payroll group, or bank code/name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Advice number, checkoff number, employer code/name, payroll group, bank code/name, or user who captured/posted/created/modified/reopened to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_advice_details",
        "description": "Search records in the cr_checkoff_advice_details table (external MySQL database) by advice number, payroll number, client code, client name, transaction type, deduction code, description, loan number, loan product, employer code, ID number, account type, FOSA account, or reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Advice number, payroll number, client code/name, transaction type, deduction code, description, loan number/product, employer code, ID number, account type, FOSA account, or reference to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_advice_imports",
        "description": "Search records in the cr_checkoff_advice_imports table (external MySQL database) by advice number or member number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Advice number or member number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_advice_line",
        "description": "Search records in the cr_checkoff_advice_line table (external MySQL database) by advice number, payroll number, client code/name, transaction type, deduction code, description, loan number/product, employer code, ID number, account type, FOSA account, reference, or comments.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Advice number, payroll number, client code/name, transaction type, deduction code, description, loan number/product, employer code, ID number, account type, FOSA account, reference, or comments to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_allocations",
        "description": "Search records in the cr_checkoff_allocations table (external MySQL database) by allocation number, advice number, deduction code, transaction type, receipt category, GL account, loan number, client code/name, dimension codes, remarks, loan product, or FOSA account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Allocation number, advice number, deduction code, transaction type, receipt category, GL account, loan number, client code/name, dimension code, remarks, loan product, or FOSA account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_defaulters",
        "description": "Search records in the cr_checkoff_defaulters table (external MySQL database) by document number, member number/name, payroll number, checkoff number, employer code/name, account number/name, posting bank, or user ID/name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, member number/name, payroll number, checkoff number, employer code/name, account number/name, posting bank, or user ID/name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_defaulters_header",
        "description": "Search records in the cr_checkoff_defaulters_header table (external MySQL database) by defaulter header number, checkoff number, employer code/name, account number/name, posting bank, or user ID/name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Defaulter header number, checkoff number, employer code/name, account number/name, posting bank, or user ID/name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_defaulters_simunye",
        "description": "Search records in the cr_checkoff_defaulters_simunye table (external MySQL database) by member number or payroll number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number or payroll number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_header",
        "description": "Search records in the cr_checkoff_header table (external MySQL database) by checkoff header number, advice number, reversal number, captured by, remarks, GSL number, account type/number/name, document number, dimension codes, employer code/name, checkoff type/account, posted by, reopened by, created by, modified by, or loan product.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Checkoff header number, advice/reversal number, captured/created/modified/reopened/posted by, remarks, GSL number, account details, document number, dimension code, employer code/name, checkoff type/account, or loan product to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_line",
        "description": "Search records in the cr_checkoff_line table (external MySQL database) by checkoff line number, advice number, payroll number, client code/name, transaction type, loan/saving product code, description, loan number, employer code, ID number, account type, FOSA account, reference, or LDA.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Checkoff line number, advice number, payroll number, client code/name, transaction type, loan/saving product code, description, loan number, employer code, ID number, account type, FOSA account, reference, or LDA to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_statistics",
        "description": "Search records in the cr_checkoff_statistics table (external MySQL database) by statistics number, client code, transaction type, loan number, loan product, or FOSA account.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Statistics number, client code, transaction type, loan number, loan product, or FOSA account to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_checkoff_summary",
        "description": "Search records in the cr_checkoff_summary table (external MySQL database) by summary number, payroll number, client code/name, transaction type, deduction code, description, loan number/product, employer code, ID number, account type, FOSA account, or reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Summary number, payroll number, client code/name, transaction type, deduction code, description, loan number/product, employer code, ID number, account type, FOSA account, or reference to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_dividend_withdrawal_charges",
        "description": "Search records in the cr_dividend_withdrawal_charges table (external MySQL database) by lower_limit, upper_limit, or charge value.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Lower limit, upper limit, or charge amount to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_dividends_manual_appraisal",
        "description": "Search records in the cr_dividends_manual_appraisal table (external MySQL database) by member number or member name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Member number or member name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_employer_payroll_groups",
        "description": "Search records in the cr_employer_payroll_groups table (external MySQL database) by document number, employer code, or employer name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Document number, employer code, or employer name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_employers",
        "description": "Search records in the cr_employers table (external MySQL database) by employer code, description, or associated customer number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Employer code, description, or customer number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_ewallet_transfer_charges",
        "description": "Search records in the cr_ewallet_transfer_charges table (external MySQL database) by charge band name, lower limit, upper limit, or charge amount.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Band name, lower limit, upper limit, or charge amount to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fixed_deposits",
        "description": "Search records in the cr_fixed_deposits table (external MySQL database) by deposit number, member number, member name, ID number, mobile number, deposit type, certificate number, or captured by user.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Deposit number, member number/name, ID number, mobile number, deposit type, certificate number, or captured by user to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fo_interest_header",
        "description": "Search records in the cr_fo_interest_header table (external MySQL database) by FO interest header number, captured by, posted by, calculation type, or remarks.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Header number, user who captured/posted, calculation type, or remarks to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fo_interest_lines",
        "description": "Search records in the cr_fo_interest_lines table (external MySQL database) by header number, member number, member name, FO account number, or mobile number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Header number, member number/name, FO account number, or mobile number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fosa_accrual_header",
        "description": "Search records in the cr_fosa_accrual_header table (external MySQL database) by accrual number, captured by, posted by, accrual type, BO group, employer code/description, or reversed by.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Accrual number, captured by, posted by, accrual type, BO group, employer code/description, or reversed by to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fosa_accrual_line",
        "description": "Search records in the cr_fosa_accrual_line table (external MySQL database) by accrual number, client code/name, loan number, loan product, GL account, payroll number, accrual type, action type, or FOSA account number.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Accrual number, client code/name, loan number/product, GL account, payroll number, accrual/action type, or FOSA account number to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fosa_standing_lines",
        "description": "Search records in the cr_fosa_standing_lines table (external MySQL database) by standing order number, account type, destination client code/name, or description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Standing order number, account type, destination client code/name, or description to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cr_fosa_trans_charges",
        "description": "Search records in the cr_fosa_trans_charges table (external MySQL database) by charge name, account number, or transaction ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Charge name, account number, or transaction ID to search for.",
                },
            },
            "required": ["query"],
        },
    },
]

# ── System prompt – gives the AI context about the SACCO & how to behave. ──

SYSTEM_PROMPT = (
    "You are UmojaAI, an expert AI assistant for UmojaFunds SACCO (Savings and Credit Cooperative) in Kenya.\n\n"
    "CONTEXT:\n"
    "- A cooperative finance organization serving East African members\n"
    "- Operates in Kenyan Shillings (KES)\n"
    "- Integrated with M-Pesa for mobile money transactions\n"
    "- Regulated by SASRA (Sacco Societies Regulatory Authority)\n\n"
    "CAPABILITIES:\n"
    "You have access to the following tools to query data ON DEMAND from the database. "
    "Use them whenever you need specific information. Do NOT make up data — use the tools to get real data.\n\n"
    "RULES:\n"
    "- Always reference amounts in Kenyan Shillings (KES)\n"
    "- Use K for thousands, M for millions (e.g. KES 1.2M)\n"
    "- Use 2026 as the current year\n"
    "- Reference SASRA regulatory standards when discussing NPL ratios (3.5%% threshold)\n"
    "- Be specific with member names, loan IDs, and transaction references\n"
    "- Provide actionable recommendations for SACCO administrators\n"
    "- Consider M-Pesa integration when discussing payment channels\n"
    "- Format responses in clear Markdown with bullet points and sections\n"
    "- Be concise but thorough; SACCO admins need quick insights\n"
    "- If a tool returns no data or fails, say so instead of guessing\n"
    "- Use the get_member_intelligence tool for specific member lookups in the external MySQL database (cr_bo_accounts, cr_loans)\n"
    "- Database access is live and strictly read-only. Never attempt to create, update, delete, approve, post, reverse, or otherwise modify records.\n"
    "- Use query_alazar to search the Alazar table in the external MySQL database by admission number (adm_no) or mobile_number\n"
    "- Use query_item_tracking_lines to search the Item_Tracking_lines table in the external MySQL database by stocktake code, item code, package code, or description\n"
    "- Use query_loan_disbursement_dates to search the Loan_disbursement_dates table in the external MySQL database by loan number (Loan_no)\n"
    "- Use query_payslip_details to search the Payslip_details table in the external MySQL database by employer code, payroll number, member name, or ID number\n"
    "- Use query_stock_taking_header to search the Stock_Taking_Setup_Header table in the external MySQL database by Code, Description, or Status\n"
    "- Use query_address_update to search the address_update table by member number (mno) or address\n"
    "- Use query_advance_loans to search the advance_loans table by user_id, teacher_id, name, or status\n"
    "- Use query_ahadi_paye to search the ahadi_paye table by staff number (staff_no)\n"
    "- Use query_airtel_discounts to search the airtel_discounts table by discount_id or status\n"
    "- Use query_airtime_merchant_logs to search the airtime_merchant_logs table by type or loaded_by\n"
    "- Use query_all_nationsdetails to search the all_nationsdetails table by member_no or group_code\n"
    "- Use query_assessment_books to search the assessment_books table by class, subject, or file info\n"
    "- Use query_attendance_lines to search the attendance_lines table by admin_no, name, or status\n"
    "- Use query_barter_transactions to search the barter_transactions table by document number or account\n"
    "- Use query_biodata_rainforest to search the biodata_rainforest table by member number, ID, or phone\n"
    "- Use query_book_assignments to search the book_assignments table by book number, student name, or admission\n"
    "- Use query_books to search the books table by title, author, book number, or subject\n"
    "- Use query_braun to search the braun table by ID number (id_no)\n"
    "- Use query_bu_commitees, query_bu_requisition_header, query_bu_requisition_lines to search business unit committees and requisitions\n"
    "- Use query_budget, query_budget_allocations, query_budget_line to search budget records and allocations\n"
    "- Use query_calender_of_events to search the calendar of events\n"
    "- Use query_cash_flow_forecast, query_cash_forecast_allocations, query_cash_forecast_line to search cash flow forecasts\n"
    "- Use query_cash_receipts to search cash receipts\n"
    "- Use query_cat_questions, query_category_types to search exam questions and category types\n"
    "- Use query_cbk_transfers to search CBK (cheque book) transfers\n"
    "- Use query_cbo_members to search CBO group members\n"
    "- Use query_cft_income_accrual_lines, query_cft_income_accruals to search income accruals\n"
    "- Use query_ci_sessions to search CodeIgniter sessions\n"
    "- Use query_closing_interest_siginon to search closing interest sign-on records\n"
    "- Use query_co_imprest_requisition_lines, query_co_imprest_requisitions, query_co_imprest_surrender, query_co_imprest_surrender_lines, query_co_imprest_surrender_linesold, query_co_imprest_surrenderold to search imprest requisitions and surrenders\n"
    "- Use query_coa_groups, query_coa_sub_groups to search chart of account groups\n"
    "- Use query_coop_lines to search cooperative customer memo lines\n"
    "- Use query_correction_deposits to search correction deposits\n"
    "- Use query_cr_loan_amount_bands, query_cr_account_types to search loan amount bands and account types\n"
    "- To get ALL records from any table, use the query tool with the word 'all', 'list', '*', or leave the query empty. For example: query with 'all' lists everything from that table.\n"
    "- Use query_members, query_loans, query_transactions, and get_portfolio_summary for internal database queries"
)

# ── Authentication ────────────────────────────────────────────────────────

def require_ai_query_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_ai_read_only_db),
) -> User:
    """Authenticate the user for AI query access via Bearer token or env admin token."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    env_admin = user_from_env_admin_token(credentials.credentials)
    if env_admin:
        return env_admin

    token = db.query(AuthToken).filter(AuthToken.token_hash == hash_token(credentials.credentials)).first()
    now = datetime.utcnow()
    if not token or token.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    last_seen = token.last_seen_at or token.created_at
    if last_seen + timedelta(minutes=SESSION_IDLE_MINUTES) < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = token.user
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not active")

    return user


# ── Internal-database query handlers ──────────────────────────────────────

def _query_members(args: dict, db: Session) -> dict:
    """Search members in the internal SQLite database."""
    query = db.query(Member)
    if status_filter := args.get("status"):
        query = query.filter(Member.status == status_filter)
    if search := args.get("search"):
        term = f"%{search}%"
        query = query.filter(Member.name.ilike(term) | Member.id.ilike(term))
    limit = min(args.get("limit", 50), 200)
    members = query.order_by(Member.id.asc()).limit(limit).all()
    return {
        "count": len(members),
        "members": [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "savings": float(m.savings),
                "loans": float(m.loans),
                "status": m.status,
                "joined": m.joined,
                "shares": m.shares,
            }
            for m in members
        ],
    }


def _query_loans(args: dict, db: Session) -> dict:
    """Search loans in the internal SQLite database."""
    query = db.query(Loan)
    if status_filter := args.get("status"):
        query = query.filter(Loan.status == status_filter)
    if member_id := args.get("member_id"):
        query = query.filter(Loan.member_id == member_id)
    limit = min(args.get("limit", 50), 200)
    loans = query.order_by(Loan.issued.desc()).limit(limit).all()
    return {
        "count": len(loans),
        "loans": [
            {
                "id": l.id,
                "member_id": l.member_id,
                "member_name": l.member.name if l.member else "",
                "amount": float(l.amount),
                "balance": float(l.balance),
                "rate": float(l.rate),
                "issued": l.issued,
                "due": l.due,
                "status": l.status,
                "type": l.type,
            }
            for l in loans
        ],
    }


def _query_transactions(args: dict, db: Session) -> dict:
    """Search transactions in the internal SQLite database."""
    query = db.query(Transaction)
    if txn_type := args.get("type"):
        query = query.filter(Transaction.type == txn_type)
    if member_id := args.get("member_id"):
        query = query.filter(Transaction.member_id == member_id)
    if category := args.get("category"):
        query = query.filter(Transaction.category.ilike(f"%{category}%"))
    limit = min(args.get("limit", 50), 200)
    transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all()
    return {
        "count": len(transactions),
        "transactions": [
            {
                "id": t.id,
                "member_id": t.member_id,
                "member_name": t.member.name if t.member else "",
                "amount": float(t.amount),
                "type": t.type,
                "category": t.category,
                "date": t.date,
                "channel": t.channel,
                "ref": t.ref,
            }
            for t in transactions
        ],
    }


def _member_intelligence(args: dict, db: Session) -> dict:
    """Look up a member in the external MySQL database (cr_bo_accounts / cr_loans)."""
    query_str = args.get("query", "").strip()
    if len(query_str) < 3:
        return {"error": "Query must be at least 3 characters"}
    try:
        result = get_member_intelligence(db, query_str)
        return result
    except HTTPException as exc:
        return {"error": exc.detail}
    except Exception as exc:
        logger.exception("Member intelligence lookup failed for %s", query_str)
        return {"error": f"Lookup failed: {exc}"}


def _portfolio_summary(args: dict, db: Session) -> dict:
    """Aggregate portfolio summary from the internal database."""
    members = db.query(Member).all()
    loans = db.query(Loan).all()
    transactions = db.query(Transaction).all()
    snapshot = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.id.desc()).first()

    total_savings = float(snapshot.savings) if snapshot else sum(float(m.savings) for m in members)
    total_loans_outstanding = float(snapshot.loans) if snapshot else sum(float(l.balance) for l in loans)
    active_members = sum(1 for m in members if m.status == "Active")
    overdue_loans = [l for l in loans if l.status == "Overdue"]
    overdue_amount = sum(float(l.balance) for l in overdue_loans)
    npl_ratio = round((overdue_amount / total_loans_outstanding * 100), 1) if total_loans_outstanding > 0 else 0.0
    total_credits = sum(float(t.amount) for t in transactions if t.type == "Credit")
    total_debits = sum(float(t.amount) for t in transactions if t.type == "Debit")

    return {
        "total_savings": round(total_savings, 2),
        "total_loans_outstanding": round(total_loans_outstanding, 2),
        "total_loans_disbursed": round(sum(float(l.amount) for l in loans), 2),
        "active_members": active_members,
        "total_members": len(members),
        "overdue_loans_count": len(overdue_loans),
        "overdue_loans_amount": round(overdue_amount, 2),
        "npl_ratio": npl_ratio,
        "total_loans": len(loans),
        "total_transactions": len(transactions),
        "recent_credit_volume": round(total_credits, 2),
        "recent_debit_volume": round(total_debits, 2),
        "latest_snapshot_month": snapshot.month if snapshot else None,
    }


# ── External MySQL table query handlers (via factory) ─────────────────────

def _make_table_handler(get_fn):
    """Factory that creates a uniform query handler wrapping a service function.

    Each generated handler extracts the ``query`` argument from the caller,
    delegates to the wrapped ``get_fn``, and standardises error handling.
    """
    def handler(args: dict, db: Session) -> dict:
        query_str = args.get("query", "").strip()
        try:
            result = get_fn(db, query_str)
            return result
        except HTTPException as exc:
            return {"error": exc.detail}
        except Exception as exc:
            fn_name = getattr(get_fn, '__name__', str(get_fn))
            logger.exception("%s lookup failed for %s", fn_name, query_str)
            return {"error": f"{fn_name} lookup failed: {exc}"}
    return handler


_alazar_query = _make_table_handler(get_alazar_records)
_item_tracking_query = _make_table_handler(get_item_tracking_lines)
_loan_disbursement_query = _make_table_handler(get_loan_disbursement_dates)
_payslip_query = _make_table_handler(get_payslip_details)
_stock_taking_header_query = _make_table_handler(get_stock_taking_header)
_address_update_query = _make_table_handler(get_address_update)
_advance_loans_query = _make_table_handler(get_advance_loans)
_ahadi_paye_query = _make_table_handler(get_ahadi_paye)
_airtel_discounts_query = _make_table_handler(get_airtel_discounts)
_airtime_merchant_logs_query = _make_table_handler(get_airtime_merchant_logs)
_all_nationsdetails_query = _make_table_handler(get_all_nationsdetails)
_assessment_books_query = _make_table_handler(get_assessment_books)
_attendance_lines_query = _make_table_handler(get_attendance_lines)
_barter_transactions_query = _make_table_handler(get_barter_transactions)
_biodata_rainforest_query = _make_table_handler(get_biodata_rainforest)
_book_assignments_query = _make_table_handler(get_book_assignments)
_books_query = _make_table_handler(get_books)
_braun_query = _make_table_handler(get_braun)
_bu_commitees_query = _make_table_handler(get_bu_commitees)
_bu_requisition_header_query = _make_table_handler(get_bu_requisition_header)
_bu_requisition_lines_query = _make_table_handler(get_bu_requisition_lines)
_budget_query = _make_table_handler(get_budget)
_budget_allocations_query = _make_table_handler(get_budget_allocations)
_budget_line_query = _make_table_handler(get_budget_line)
_calender_of_events_query = _make_table_handler(get_calender_of_events)
_cash_flow_forecast_query = _make_table_handler(get_cash_flow_forecast)
_cash_forecast_allocations_query = _make_table_handler(get_cash_forecast_allocations)
_cash_forecast_line_query = _make_table_handler(get_cash_forecast_line)
_cash_receipts_query = _make_table_handler(get_cash_receipts)
_cat_questions_query = _make_table_handler(get_cat_questions)
_category_types_query = _make_table_handler(get_category_types)
_cbk_transfers_query = _make_table_handler(get_cbk_transfers)
_cbo_members_query = _make_table_handler(get_cbo_members)
_cft_income_accrual_lines_query = _make_table_handler(get_cft_income_accrual_lines)
_cft_income_accruals_query = _make_table_handler(get_cft_income_accruals)
_ci_sessions_query = _make_table_handler(get_ci_sessions)
_closing_interest_siginon_query = _make_table_handler(get_closing_interest_siginon)
_co_imprest_requisition_lines_query = _make_table_handler(get_co_imprest_requisition_lines)
_co_imprest_requisitions_query = _make_table_handler(get_co_imprest_requisitions)
_co_imprest_surrender_query = _make_table_handler(get_co_imprest_surrender)
_co_imprest_surrender_lines_query = _make_table_handler(get_co_imprest_surrender_lines)
_co_imprest_surrender_linesold_query = _make_table_handler(get_co_imprest_surrender_linesold)
_co_imprest_surrenderold_query = _make_table_handler(get_co_imprest_surrenderold)
_coa_groups_query = _make_table_handler(get_coa_groups)
_coa_sub_groups_query = _make_table_handler(get_coa_sub_groups)
_coop_lines_query = _make_table_handler(get_coop_lines)
_correction_deposits_query = _make_table_handler(get_correction_deposits)
_cr_loan_amount_bands_query = _make_table_handler(get_cr_loan_amount_bands)
_cr_account_types_query = _make_table_handler(get_cr_account_types)
_cr_accrual_header_query = _make_table_handler(get_cr_accrual_header)
_cr_accrual_line_query = _make_table_handler(get_cr_accrual_line)
_cr_arrears_offset_query = _make_table_handler(get_cr_arrears_offset)
_cr_banking_agents_query = _make_table_handler(get_cr_banking_agents)
_cr_bo_accounts_nos_query = _make_table_handler(get_cr_bo_accounts_nos)
_cr_bo_applications_query = _make_table_handler(get_cr_bo_applications)
_cr_bo_applications_old_query = _make_table_handler(get_cr_bo_applications_old)
_cr_bo_charges_query = _make_table_handler(get_cr_bo_charges)
_cr_bo_departments_query = _make_table_handler(get_cr_bo_departments)
_cr_bo_deposit_classification_query = _make_table_handler(get_cr_bo_deposit_classification)
_cr_bo_general_setup_query = _make_table_handler(get_cr_bo_general_setup)
_cr_bo_insider_borrowers_query = _make_table_handler(get_cr_bo_insider_borrowers)
_cr_bo_ledger_entry_query = _make_table_handler(get_cr_bo_ledger_entry)
_cr_bo_mobile_applications_query = _make_table_handler(get_cr_bo_mobile_applications)
_cr_bo_posting_group_query = _make_table_handler(get_cr_bo_posting_group)
_cr_bosa_standing_lines_query = _make_table_handler(get_cr_bosa_standing_lines)
_cr_business_types_query = _make_table_handler(get_cr_business_types)
_cr_checkoff_advice_query = _make_table_handler(get_cr_checkoff_advice)
_cr_checkoff_advice_details_query = _make_table_handler(get_cr_checkoff_advice_details)
_cr_checkoff_advice_imports_query = _make_table_handler(get_cr_checkoff_advice_imports)
_cr_checkoff_advice_line_query = _make_table_handler(get_cr_checkoff_advice_line)
_cr_checkoff_allocations_query = _make_table_handler(get_cr_checkoff_allocations)
_cr_checkoff_defaulters_query = _make_table_handler(get_cr_checkoff_defaulters)
_cr_checkoff_defaulters_header_query = _make_table_handler(get_cr_checkoff_defaulters_header)
_cr_checkoff_defaulters_simunye_query = _make_table_handler(get_cr_checkoff_defaulters_simunye)
_cr_checkoff_header_query = _make_table_handler(get_cr_checkoff_header)
_cr_checkoff_line_query = _make_table_handler(get_cr_checkoff_line)
_cr_checkoff_statistics_query = _make_table_handler(get_cr_checkoff_statistics)
_cr_checkoff_summary_query = _make_table_handler(get_cr_checkoff_summary)

# --- New MySQL table handlers ---
_cr_dividend_withdrawal_charges_query = _make_table_handler(get_cr_dividend_withdrawal_charges)
_cr_dividends_manual_appraisal_query = _make_table_handler(get_cr_dividends_manual_appraisal)
_cr_employer_payroll_groups_query = _make_table_handler(get_cr_employer_payroll_groups)
_cr_employers_query = _make_table_handler(get_cr_employers)
_cr_ewallet_transfer_charges_query = _make_table_handler(get_cr_ewallet_transfer_charges)
_cr_fixed_deposits_query = _make_table_handler(get_cr_fixed_deposits)
_cr_fo_interest_header_query = _make_table_handler(get_cr_fo_interest_header)
_cr_fo_interest_lines_query = _make_table_handler(get_cr_fo_interest_lines)
_cr_fosa_accrual_header_query = _make_table_handler(get_cr_fosa_accrual_header)
_cr_fosa_accrual_line_query = _make_table_handler(get_cr_fosa_accrual_line)
_cr_fosa_standing_lines_query = _make_table_handler(get_cr_fosa_standing_lines)
_cr_fosa_trans_charges_query = _make_table_handler(get_cr_fosa_trans_charges)


# ── Function dispatcher ───────────────────────────────────────────────────

def _execute_function(name: str, args: dict, db: Session) -> dict:
    """Look up *name* in the function map and call it with *args* + *db*."""
    fn_map = {
        "query_members": _query_members,
        "query_loans": _query_loans,
        "query_transactions": _query_transactions,
        "get_member_intelligence": _member_intelligence,
        "get_portfolio_summary": _portfolio_summary,
        "query_alazar": _alazar_query,
        "query_item_tracking_lines": _item_tracking_query,
        "query_loan_disbursement_dates": _loan_disbursement_query,
        "query_payslip_details": _payslip_query,
        "query_stock_taking_header": _stock_taking_header_query,
        "query_address_update": _address_update_query,
        "query_advance_loans": _advance_loans_query,
        "query_ahadi_paye": _ahadi_paye_query,
        "query_airtel_discounts": _airtel_discounts_query,
        "query_airtime_merchant_logs": _airtime_merchant_logs_query,
        "query_all_nationsdetails": _all_nationsdetails_query,
        "query_assessment_books": _assessment_books_query,
        "query_attendance_lines": _attendance_lines_query,
        "query_barter_transactions": _barter_transactions_query,
        "query_biodata_rainforest": _biodata_rainforest_query,
        "query_book_assignments": _book_assignments_query,
        "query_books": _books_query,
        "query_braun": _braun_query,
        "query_bu_commitees": _bu_commitees_query,
        "query_bu_requisition_header": _bu_requisition_header_query,
        "query_bu_requisition_lines": _bu_requisition_lines_query,
        "query_budget": _budget_query,
        "query_budget_allocations": _budget_allocations_query,
        "query_budget_line": _budget_line_query,
        "query_calender_of_events": _calender_of_events_query,
        "query_cash_flow_forecast": _cash_flow_forecast_query,
        "query_cash_forecast_allocations": _cash_forecast_allocations_query,
        "query_cash_forecast_line": _cash_forecast_line_query,
        "query_cash_receipts": _cash_receipts_query,
        "query_cat_questions": _cat_questions_query,
        "query_category_types": _category_types_query,
        "query_cbk_transfers": _cbk_transfers_query,
        "query_cbo_members": _cbo_members_query,
        "query_cft_income_accrual_lines": _cft_income_accrual_lines_query,
        "query_cft_income_accruals": _cft_income_accruals_query,
        "query_ci_sessions": _ci_sessions_query,
        "query_closing_interest_siginon": _closing_interest_siginon_query,
        "query_co_imprest_requisition_lines": _co_imprest_requisition_lines_query,
        "query_co_imprest_requisitions": _co_imprest_requisitions_query,
        "query_co_imprest_surrender": _co_imprest_surrender_query,
        "query_co_imprest_surrender_lines": _co_imprest_surrender_lines_query,
        "query_co_imprest_surrender_linesold": _co_imprest_surrender_linesold_query,
        "query_co_imprest_surrenderold": _co_imprest_surrenderold_query,
        "query_coa_groups": _coa_groups_query,
        "query_coa_sub_groups": _coa_sub_groups_query,
        "query_coop_lines": _coop_lines_query,
        "query_correction_deposits": _correction_deposits_query,
        "query_cr_loan_amount_bands": _cr_loan_amount_bands_query,
        "query_cr_account_types": _cr_account_types_query,
        "query_cr_accrual_header": _cr_accrual_header_query,
        "query_cr_accrual_line": _cr_accrual_line_query,
        "query_cr_arrears_offset": _cr_arrears_offset_query,
        "query_cr_banking_agents": _cr_banking_agents_query,
        "query_cr_bo_accounts_nos": _cr_bo_accounts_nos_query,
        "query_cr_bo_applications": _cr_bo_applications_query,
        "query_cr_bo_applications_old": _cr_bo_applications_old_query,
        "query_cr_bo_charges": _cr_bo_charges_query,
        "query_cr_bo_departments": _cr_bo_departments_query,
        "query_cr_bo_deposit_classification": _cr_bo_deposit_classification_query,
        "query_cr_bo_general_setup": _cr_bo_general_setup_query,
        "query_cr_bo_insider_borrowers": _cr_bo_insider_borrowers_query,
        "query_cr_bo_ledger_entry": _cr_bo_ledger_entry_query,
        "query_cr_bo_mobile_applications": _cr_bo_mobile_applications_query,
        "query_cr_bo_posting_group": _cr_bo_posting_group_query,
        "query_cr_bosa_standing_lines": _cr_bosa_standing_lines_query,
        "query_cr_business_types": _cr_business_types_query,
        "query_cr_checkoff_advice": _cr_checkoff_advice_query,
        "query_cr_checkoff_advice_details": _cr_checkoff_advice_details_query,
        "query_cr_checkoff_advice_imports": _cr_checkoff_advice_imports_query,
        "query_cr_checkoff_advice_line": _cr_checkoff_advice_line_query,
        "query_cr_checkoff_allocations": _cr_checkoff_allocations_query,
        "query_cr_checkoff_defaulters": _cr_checkoff_defaulters_query,
        "query_cr_checkoff_defaulters_header": _cr_checkoff_defaulters_header_query,
        "query_cr_checkoff_defaulters_simunye": _cr_checkoff_defaulters_simunye_query,
        "query_cr_checkoff_header": _cr_checkoff_header_query,
        "query_cr_checkoff_line": _cr_checkoff_line_query,
        "query_cr_checkoff_statistics": _cr_checkoff_statistics_query,
        "query_cr_checkoff_summary": _cr_checkoff_summary_query,
        "query_cr_dividend_withdrawal_charges": _cr_dividend_withdrawal_charges_query,
        "query_cr_dividends_manual_appraisal": _cr_dividends_manual_appraisal_query,
        "query_cr_employer_payroll_groups": _cr_employer_payroll_groups_query,
        "query_cr_employers": _cr_employers_query,
        "query_cr_ewallet_transfer_charges": _cr_ewallet_transfer_charges_query,
        "query_cr_fixed_deposits": _cr_fixed_deposits_query,
        "query_cr_fo_interest_header": _cr_fo_interest_header_query,
        "query_cr_fo_interest_lines": _cr_fo_interest_lines_query,
        "query_cr_fosa_accrual_header": _cr_fosa_accrual_header_query,
        "query_cr_fosa_accrual_line": _cr_fosa_accrual_line_query,
        "query_cr_fosa_standing_lines": _cr_fosa_standing_lines_query,
        "query_cr_fosa_trans_charges": _cr_fosa_trans_charges_query,
    }
    fn = fn_map.get(name)
    if not fn:
        return {"error": f"Unknown function: {name}"}
    try:
        result = fn(args, db)
        return {"result": result}
    except Exception as exc:
        logger.exception("Function %s failed", name)
        return {"error": str(exc)}


# ── Gemini helpers ────────────────────────────────────────────────────────

def _gemini_url() -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


async def _gemini_request(payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _gemini_url(),
            json=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
            timeout=60.0,
        )
    if not resp.is_success:
        detail = f"Gemini API error: {resp.status_code}"
        try:
            err = resp.json()
            detail = err.get("error", {}).get("message", detail)
        except Exception:
            detail = resp.text or detail
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return resp.json()


# ── Main chat endpoint ────────────────────────────────────────────────────

@router.post("/chat")
async def ai_chat(
    request: Request,
    user: "User" = Depends(require_ai_query_user),
    db: Session = Depends(get_ai_read_only_db),
):
    """Chat with the AI assistant.  The backend handles Gemini function calling
    so the AI can query the database on demand."""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API key not configured on the server",
        )

    body = await request.json()
    message: str = body.get("message", "")
    conversation_history: list[dict] = body.get("conversation_history", [])

    if not message.strip():
        raise HTTPException(status_code=400, detail="Message is required")

    # Build Gemini contents array from conversation history
    contents: list[dict] = []
    for msg in conversation_history:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    base_payload: dict = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "tools": [{"functionDeclarations": TOOL_DEFINITIONS}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
        },
    }

    # ── Function calling loop (max 8 rounds) ────────────────────────────
    for _ in range(8):
        payload: dict = {**base_payload, "contents": contents}
        result = await _gemini_request(payload)

        candidate = (result.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []

        # Collect text parts (Gemini may return text + function calls together)
        text_parts = [p.get("text", "") for p in parts if "text" in p]
        function_calls = [p.get("functionCall") for p in parts if "functionCall" in p]

        if not function_calls:
            # No more function calls — text response is ready
            final_text = "".join(text_parts).strip()
            return {"content": final_text or "I'm not sure how to answer that. Could you rephrase?"}

        # Execute each function call and append to contents
        for fc in function_calls:
            fn_name: str = fc.get("name", "")
            fn_args: dict = fc.get("args") or {}
            logger.info("Gemini called function: %s args=%s", fn_name, fn_args)

            fn_result = _execute_function(fn_name, fn_args, db)

            # Append the model's function call request
            contents.append({
                "role": "model",
                "parts": [{"functionCall": {"name": fn_name, "args": fn_args}}],
            })
            # Append the function response
            contents.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": fn_name,
                            "response": {
                                "name": fn_name,
                                "content": fn_result,
                            },
                        }
                    }
                ],
            })

    # If we exhaust rounds without a final text, return whatever text we have
    return {"content": "I've gathered all the information I can. Please ask a more specific question."}
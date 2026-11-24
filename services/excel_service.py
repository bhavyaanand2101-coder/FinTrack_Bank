"""
FinTrack - Smart Digital Banking & Loan Management System
Live Excel Export & Real-Time Workbook Synchronization Service
File: services/excel_service.py
"""

import datetime
from decimal import Decimal
import hashlib
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import uuid

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from database_layer.postgres import fetch_all, fetch_one

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCEL_PATH = PROJECT_ROOT / "fintrack_live_data.xlsx"

# Styling palette (Modern Banking Navy & Slate)
HEADER_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="0F172A")
SUBTITLE_FONT = Font(name="Calibri", size=10, italic=True, color="475569")
ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
WHITE_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

GREEN_FILL = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
GREEN_FONT = Font(name="Calibri", size=10, bold=True, color="166534")
AMBER_FILL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
AMBER_FONT = Font(name="Calibri", size=10, bold=True, color="92400E")
RED_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
RED_FONT = Font(name="Calibri", size=10, bold=True, color="991B1B")

BODY_FONT = Font(name="Calibri", size=10, color="1E293B")
BOLD_FONT = Font(name="Calibri", size=10, bold=True, color="0F172A")

THIN_BORDER = Border(
    left=Side(style="thin", color="E2E8F0"),
    right=Side(style="thin", color="E2E8F0"),
    top=Side(style="thin", color="E2E8F0"),
    bottom=Side(style="thin", color="E2E8F0"),
)

CURRENCY_COLUMNS = {
    "balance",
    "amount",
    "transfer_amount",
    "requested_amount",
    "annual_income",
    "total_incoming_amount",
    "total_outgoing_amount",
}

STATUS_COLUMNS = {"status", "alert_status", "tx_status", "transaction_status", "is_frozen", "entry_type"}


def _clean_cell_value(val: Any) -> Any:
    """Convert PostgreSQL types (Decimal, datetime, UUID, dict) to Excel-safe values."""
    if val is None:
        return ""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime.datetime, datetime.date)):
        if isinstance(val, datetime.datetime):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        return val.strftime("%Y-%m-%d")
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, (dict, list)):
        text = json.dumps(val, default=str)
        return text[:30000]  # Excel cell character limit safeguard
    return val


def _apply_status_style(cell, col_name: str, raw_val: Any) -> None:
    """Highlight banking status cells with semantic colors."""
    val_str = str(raw_val).upper()
    if col_name == "is_frozen":
        if raw_val is True or val_str == "TRUE":
            cell.fill = RED_FILL
            cell.font = RED_FONT
        else:
            cell.fill = GREEN_FILL
            cell.font = GREEN_FONT
        return

    if val_str in ("SUCCESS", "APPROVED", "DELIVERED", "CREDIT", "BALANCED"):
        cell.fill = GREEN_FILL
        cell.font = GREEN_FONT
    elif val_str in ("PENDING", "FLAGGED", "OPEN", "PROCESSING"):
        cell.fill = AMBER_FILL
        cell.font = AMBER_FONT
    elif val_str in ("FAILED", "REJECTED", "DEBIT"):
        cell.fill = RED_FILL
        cell.font = RED_FONT


def _write_table_sheet(
    wb: Workbook,
    title: str,
    columns: Sequence[str],
    rows: List[Dict[str, Any]],
) -> None:
    """Create and format a styled Excel worksheet from a list of dictionary rows."""
    ws = wb.create_sheet(title=title)
    ws.views.sheetView[0].showGridLines = True

    # Write header row
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name.replace("_", " ").title())
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER
    ws.row_dimensions[1].height = 24

    # Write data rows
    for row_idx, row_data in enumerate(rows, start=2):
        row_fill = ZEBRA_FILL if row_idx % 2 == 1 else WHITE_FILL
        for col_idx, col_name in enumerate(columns, start=1):
            raw_val = row_data.get(col_name)
            cleaned = _clean_cell_value(raw_val)
            cell = ws.cell(row=row_idx, column=col_idx, value=cleaned)
            cell.font = BODY_FONT
            cell.fill = row_fill
            cell.border = THIN_BORDER

            if col_name in CURRENCY_COLUMNS and isinstance(cleaned, (int, float)):
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_name in STATUS_COLUMNS:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                _apply_status_style(cell, col_name, raw_val)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # Auto-fit column widths (capped for readability)
    for col_idx, col_name in enumerate(columns, start=1):
        header_len = len(col_name) + 4
        max_len = header_len
        for row_idx in range(2, min(len(rows) + 2, 200)):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)) + 3)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len, 12), 45)

    # Freeze top header row and add autofilter
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(rows) + 1}"


class ExcelService:
    """Generates live, formatted Excel workbooks from PostgreSQL financial data."""

    @staticmethod
    def compute_database_fingerprint() -> str:
        """
        Compute a lightweight deterministic fingerprint across all 8 tables.
        Changes immediately whenever any row is inserted, updated, or deleted.
        """
        query = """
            SELECT
                (SELECT COUNT(*) || ':' || COALESCE(MAX(customer_id), 0) FROM customers) AS c_sig,
                (SELECT COUNT(*) || ':' || COALESCE(MAX(user_id), 0) || ':' || COUNT(*) FILTER (WHERE is_active) FROM users) AS u_sig,
                (SELECT COUNT(*) || ':' || COALESCE(SUM(balance), 0) || ':' || COUNT(*) FILTER (WHERE is_frozen) || ':' || COALESCE(MAX(updated_at)::text, '') FROM accounts) AS a_sig,
                (SELECT COUNT(*) || ':' || COALESCE(MAX(transaction_id), 0) || ':' || COUNT(*) FILTER (WHERE status = 'SUCCESS') || ':' || COUNT(*) FILTER (WHERE status = 'FLAGGED') || ':' || COUNT(*) FILTER (WHERE status = 'FAILED') FROM transactions) AS t_sig,
                (SELECT COUNT(*) || ':' || COALESCE(MAX(entry_id), 0) || ':' || COALESCE(SUM(amount), 0) FROM ledger_entries) AS le_sig,
                (SELECT COUNT(*) || ':' || COALESCE(MAX(loan_id), 0) || ':' || COUNT(*) FILTER (WHERE status = 'APPROVED') || ':' || COUNT(*) FILTER (WHERE status = 'REJECTED') || ':' || COALESCE(MAX(reviewed_at)::text, '') FROM loans) AS l_sig,
                (SELECT COUNT(*) || ':' || COALESCE(MAX(alert_id), 0) || ':' || COUNT(*) FILTER (WHERE status = 'OPEN') || ':' || COALESCE(MAX(reviewed_at)::text, '') FROM fraud_alerts) AS f_sig,
                (SELECT COUNT(*) || ':' || COUNT(*) FILTER (WHERE status = 'DELIVERED') || ':' || COUNT(*) FILTER (WHERE status = 'PENDING') || ':' || COALESCE(MAX(processed_at)::text, '') FROM audit_outbox) AS ao_sig;
        """
        row = fetch_one(query)
        raw = "|".join(str(row.get(k, "")) for k in sorted(row.keys())) if row else ""
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def build_full_workbook_bytes(cls) -> bytes:
        """Query all live FinTrack tables and build a formatted multi-sheet Excel workbook."""
        wb = Workbook()
        # Use default active sheet as Executive Summary
        summary_ws = wb.active
        summary_ws.title = "Summary"

        # Fetch KPI metrics
        kpis = fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM customers) AS total_customers,
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(*) FROM accounts) AS total_accounts,
                (SELECT COUNT(*) FROM accounts WHERE is_frozen = TRUE) AS frozen_accounts,
                (SELECT COALESCE(SUM(balance), 0.00) FROM accounts) AS total_bank_deposits,
                (SELECT COUNT(*) FROM transactions) AS total_transactions,
                (SELECT COUNT(*) FROM transactions WHERE status = 'SUCCESS') AS successful_transactions,
                (SELECT COUNT(*) FROM transactions WHERE status = 'FLAGGED') AS flagged_transactions,
                (SELECT COALESCE(SUM(amount), 0.00) FROM transactions WHERE status = 'SUCCESS') AS total_volume,
                (SELECT COALESCE(SUM(amount), 0.00) FROM ledger_entries WHERE entry_type = 'DEBIT') AS total_debits,
                (SELECT COALESCE(SUM(amount), 0.00) FROM ledger_entries WHERE entry_type = 'CREDIT') AS total_credits,
                (SELECT COUNT(*) FROM loans WHERE status = 'PENDING') AS pending_loans,
                (SELECT COUNT(*) FROM loans WHERE status = 'APPROVED') AS approved_loans,
                (SELECT COUNT(*) FROM fraud_alerts WHERE status = 'OPEN') AS open_fraud_alerts,
                (SELECT COUNT(*) FROM audit_outbox WHERE status = 'DELIVERED') AS delivered_audit_events,
                (SELECT COUNT(*) FROM audit_outbox WHERE status = 'PENDING') AS pending_audit_events;
            """
        ) or {}

        # Populate Summary Sheet
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_ws["A1"] = "FinTrack — Live Banking Database Snapshot"
        summary_ws["A1"].font = TITLE_FONT
        summary_ws["A2"] = f"Auto-synced from PostgreSQL (fintrack) | Last Updated: {now_str}"
        summary_ws["A2"].font = SUBTITLE_FONT

        summary_headers = ["Metric", "Live Value", "Notes"]
        for col_idx, text in enumerate(summary_headers, start=1):
            c = summary_ws.cell(row=4, column=col_idx, value=text)
            c.fill = HEADER_FILL
            c.font = HEADER_FONT
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = THIN_BORDER
        summary_ws.row_dimensions[4].height = 24

        total_debits = Decimal(str(kpis.get("total_debits") or "0.00"))
        total_credits = Decimal(str(kpis.get("total_credits") or "0.00"))
        ledger_balanced = "BALANCED" if total_debits == total_credits else "IMBALANCED"

        summary_rows = [
            ("Total Registered Customers", kpis.get("total_customers", 0), "Active KYC records in customers table"),
            ("Total System Users", kpis.get("total_users", 0), "Admins + Customers (passwords excluded)"),
            ("Total Bank Accounts", kpis.get("total_accounts", 0), f"{kpis.get('frozen_accounts', 0)} currently frozen"),
            ("Total Bank Deposits (INR)", float(kpis.get("total_bank_deposits") or 0), "Aggregate balance across all accounts"),
            ("Total Transactions", kpis.get("total_transactions", 0), f"{kpis.get('successful_transactions', 0)} SUCCESS, {kpis.get('flagged_transactions', 0)} FLAGGED"),
            ("Successful Transfer Volume (INR)", float(kpis.get("total_volume") or 0), "Completed funds transferred"),
            ("Double-Entry Total Debits (INR)", float(total_debits), "Sum of all DEBIT ledger_entries"),
            ("Double-Entry Total Credits (INR)", float(total_credits), "Sum of all CREDIT ledger_entries"),
            ("Double-Entry Accounting Status", ledger_balanced, "Fundamental invariant: Total Debits == Total Credits"),
            ("Pending Loan Applications", kpis.get("pending_loans", 0), f"{kpis.get('approved_loans', 0)} approved loans"),
            ("Open Compliance / Fraud Holds", kpis.get("open_fraud_alerts", 0), "Transfers >= INR 10,000 awaiting admin review"),
            ("Audit Outbox Synced to MongoDB", kpis.get("delivered_audit_events", 0), f"{kpis.get('pending_audit_events', 0)} pending delivery"),
        ]

        for idx, (metric, val, note) in enumerate(summary_rows, start=5):
            fill = ZEBRA_FILL if idx % 2 == 1 else WHITE_FILL
            c1 = summary_ws.cell(row=idx, column=1, value=metric)
            c2 = summary_ws.cell(row=idx, column=2, value=val)
            c3 = summary_ws.cell(row=idx, column=3, value=note)
            for c in (c1, c2, c3):
                c.fill = fill
                c.border = THIN_BORDER
                c.font = BODY_FONT
            c1.font = BOLD_FONT
            if "(INR)" in metric:
                c2.number_format = '#,##0.00'
                c2.alignment = Alignment(horizontal="right", vertical="center")
            elif metric == "Double-Entry Accounting Status":
                c2.alignment = Alignment(horizontal="center", vertical="center")
                _apply_status_style(c2, "status", val)
            else:
                c2.alignment = Alignment(horizontal="right", vertical="center")

        summary_ws.column_dimensions["A"].width = 36
        summary_ws.column_dimensions["B"].width = 22
        summary_ws.column_dimensions["C"].width = 52
        summary_ws.freeze_panes = "A5"

        # 2. Customers Sheet
        customers = fetch_all(
            "SELECT customer_id, full_name, email, phone, created_at FROM customers ORDER BY customer_id ASC;"
        )
        _write_table_sheet(
            wb,
            "Customers",
            ["customer_id", "full_name", "email", "phone", "created_at"],
            customers,
        )

        # 3. Users Sheet (strictly excludes password_hash)
        users = fetch_all(
            "SELECT user_id, customer_id, username, role, is_active, created_at FROM users ORDER BY user_id ASC;"
        )
        _write_table_sheet(
            wb,
            "Users",
            ["user_id", "customer_id", "username", "role", "is_active", "created_at"],
            users,
        )

        # 4. Accounts Sheet (from View_Account_Summary)
        accounts = fetch_all(
            """
            SELECT account_id, customer_id, customer_name, account_type, balance, currency,
                   is_frozen, total_incoming_amount, total_outgoing_amount, total_transactions_count, created_at
            FROM View_Account_Summary
            ORDER BY account_id ASC;
            """
        )
        _write_table_sheet(
            wb,
            "Accounts",
            [
                "account_id",
                "customer_id",
                "customer_name",
                "account_type",
                "balance",
                "currency",
                "is_frozen",
                "total_incoming_amount",
                "total_outgoing_amount",
                "total_transactions_count",
                "created_at",
            ],
            accounts,
        )

        # 5. Transactions Sheet (from View_Transaction_Summary)
        transactions = fetch_all(
            """
            SELECT transaction_id, sender_account_id, sender_name, receiver_account_id, receiver_name,
                   amount, currency, status, description, transaction_date, idempotency_key
            FROM View_Transaction_Summary
            ORDER BY transaction_date DESC, transaction_id DESC;
            """
        )
        _write_table_sheet(
            wb,
            "Transactions",
            [
                "transaction_id",
                "sender_account_id",
                "sender_name",
                "receiver_account_id",
                "receiver_name",
                "amount",
                "currency",
                "status",
                "description",
                "transaction_date",
                "idempotency_key",
            ],
            transactions,
        )

        # 6. Ledger Entries Sheet
        ledger = fetch_all(
            """
            SELECT entry_id, transaction_id, account_id, entry_type, amount, created_at
            FROM ledger_entries
            ORDER BY entry_id DESC;
            """
        )
        _write_table_sheet(
            wb,
            "Ledger_Entries",
            ["entry_id", "transaction_id", "account_id", "entry_type", "amount", "created_at"],
            ledger,
        )

        # 7. Loans Sheet
        loans = fetch_all(
            """
            SELECT l.loan_id, l.customer_id, c.full_name AS customer_name, l.requested_amount,
                   l.annual_income, l.credit_score, l.interest_rate, l.status, l.applied_at, l.reviewed_at
            FROM loans l
            JOIN customers c ON l.customer_id = c.customer_id
            ORDER BY l.applied_at DESC, l.loan_id DESC;
            """
        )
        _write_table_sheet(
            wb,
            "Loans",
            [
                "loan_id",
                "customer_id",
                "customer_name",
                "requested_amount",
                "annual_income",
                "credit_score",
                "interest_rate",
                "status",
                "applied_at",
                "reviewed_at",
            ],
            loans,
        )

        # 8. Fraud Alerts Sheet (from View_Fraud_Alerts)
        fraud_alerts = fetch_all(
            """
            SELECT alert_id, transaction_id, account_id, customer_name, receiver_account_id,
                   receiver_name, transfer_amount, reason, alert_status, transaction_status,
                   alert_created_at, alert_reviewed_at
            FROM View_Fraud_Alerts
            ORDER BY alert_created_at DESC, alert_id DESC;
            """
        )
        _write_table_sheet(
            wb,
            "Fraud_Alerts",
            [
                "alert_id",
                "transaction_id",
                "account_id",
                "customer_name",
                "receiver_account_id",
                "receiver_name",
                "transfer_amount",
                "reason",
                "alert_status",
                "transaction_status",
                "alert_created_at",
                "alert_reviewed_at",
            ],
            fraud_alerts,
        )

        # 9. Audit Outbox Sheet
        outbox = fetch_all(
            """
            SELECT event_id, event_type, status, retry_count, created_at, processed_at, last_error
            FROM audit_outbox
            ORDER BY created_at DESC
            LIMIT 500;
            """
        )
        _write_table_sheet(
            wb,
            "Audit_Outbox",
            ["event_id", "event_type", "status", "retry_count", "created_at", "processed_at", "last_error"],
            outbox,
        )

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    @classmethod
    def sync_live_workbook_to_disk(cls, output_path: Path = DEFAULT_EXCEL_PATH) -> Path:
        """
        Atomically write the live Excel workbook to disk so open readers never see partial writes.
        """
        excel_bytes = cls.build_full_workbook_bytes()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(".tmp.xlsx")

        with open(temp_path, "wb") as f:
            f.write(excel_bytes)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, output_path)
        return output_path

    @classmethod
    def build_customer_workbook_bytes(cls, customer_id: int) -> bytes:
        """Build a strictly isolated Excel workbook containing only the authenticated customer's data."""
        wb = Workbook()
        wb.remove(wb.active)

        accounts = fetch_all(
            """
            SELECT account_id, account_type, balance, currency, is_frozen,
                   total_incoming_amount, total_outgoing_amount, total_transactions_count, created_at
            FROM View_Account_Summary
            WHERE customer_id = %s
            ORDER BY account_id ASC;
            """,
            (customer_id,),
        )
        _write_table_sheet(
            wb,
            "My_Accounts",
            [
                "account_id",
                "account_type",
                "balance",
                "currency",
                "is_frozen",
                "total_incoming_amount",
                "total_outgoing_amount",
                "total_transactions_count",
                "created_at",
            ],
            accounts,
        )

        transactions = fetch_all(
            """
            SELECT transaction_id, sender_account_id, sender_name, receiver_account_id, receiver_name,
                   amount, currency, status, description, transaction_date
            FROM View_Transaction_Summary
            WHERE sender_customer_id = %s OR receiver_customer_id = %s
            ORDER BY transaction_date DESC, transaction_id DESC;
            """,
            (customer_id, customer_id),
        )
        _write_table_sheet(
            wb,
            "My_Transactions",
            [
                "transaction_id",
                "sender_account_id",
                "sender_name",
                "receiver_account_id",
                "receiver_name",
                "amount",
                "currency",
                "status",
                "description",
                "transaction_date",
            ],
            transactions,
        )

        loans = fetch_all(
            """
            SELECT loan_id, requested_amount, annual_income, credit_score, interest_rate,
                   status, applied_at, reviewed_at
            FROM loans
            WHERE customer_id = %s
            ORDER BY applied_at DESC, loan_id DESC;
            """,
            (customer_id,),
        )
        _write_table_sheet(
            wb,
            "My_Loans",
            [
                "loan_id",
                "requested_amount",
                "annual_income",
                "credit_score",
                "interest_rate",
                "status",
                "applied_at",
                "reviewed_at",
            ],
            loans,
        )

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def get_live_file_status(output_path: Path = DEFAULT_EXCEL_PATH) -> Dict[str, Any]:
        """Return metadata about the live synced Excel workbook on disk."""
        p = Path(output_path)
        if not p.exists():
            return {
                "exists": False,
                "file_path": str(p),
                "size_kb": 0.0,
                "last_updated": None,
            }
        stat = p.stat()
        return {
            "exists": True,
            "file_path": str(p),
            "file_name": p.name,
            "size_kb": round(stat.st_size / 1024, 2),
            "last_updated": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

    @staticmethod
    def _serialize_rows(rows: List[Dict[str, Any]], columns: Sequence[str]) -> List[Dict[str, Any]]:
        """Serialize PostgreSQL row dicts into clean JSON-safe primitives for real-time grid rendering."""
        serialized = []
        for row in rows:
            item = {}
            for col in columns:
                item[col] = _clean_cell_value(row.get(col))
            serialized.append(item)
        return serialized

    @classmethod
    def get_admin_live_sheet_snapshot(cls) -> Dict[str, Any]:
        """Return a live multi-sheet JSON snapshot of all FinTrack tables for real-time spreadsheet view."""
        fp = cls.compute_database_fingerprint()
        kpis = fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM customers) AS total_customers,
                (SELECT COUNT(*) FROM accounts) AS total_accounts,
                (SELECT COALESCE(SUM(balance), 0.00) FROM accounts) AS total_deposits,
                (SELECT COUNT(*) FROM transactions) AS total_transactions,
                (SELECT COALESCE(SUM(amount), 0.00) FROM transactions WHERE status = 'SUCCESS') AS total_volume,
                (SELECT COALESCE(SUM(amount), 0.00) FROM ledger_entries WHERE entry_type = 'DEBIT') AS total_debits,
                (SELECT COALESCE(SUM(amount), 0.00) FROM ledger_entries WHERE entry_type = 'CREDIT') AS total_credits,
                (SELECT COUNT(*) FROM ledger_entries) AS total_ledger_entries,
                (SELECT COUNT(*) FROM loans WHERE status = 'PENDING') AS pending_loans,
                (SELECT COUNT(*) FROM fraud_alerts WHERE status = 'OPEN') AS open_fraud_alerts,
                (SELECT COUNT(*) FROM audit_outbox WHERE status = 'DELIVERED') AS delivered_outbox,
                (SELECT COUNT(*) FROM audit_outbox WHERE status = 'PENDING') AS pending_outbox;
            """
        ) or {}

        total_debits = Decimal(str(kpis.get("total_debits") or "0.00"))
        total_credits = Decimal(str(kpis.get("total_credits") or "0.00"))

        acc_cols = [
            "account_id", "customer_name", "account_type", "balance", "currency",
            "is_frozen", "total_incoming_amount", "total_outgoing_amount", "total_transactions_count",
        ]
        accounts = fetch_all(
            """
            SELECT account_id, customer_name, account_type, balance, currency, is_frozen,
                   total_incoming_amount, total_outgoing_amount, total_transactions_count
            FROM View_Account_Summary
            ORDER BY account_id ASC;
            """
        )

        tx_cols = [
            "transaction_id", "sender_account_id", "sender_name", "receiver_account_id",
            "receiver_name", "amount", "status", "description", "transaction_date",
        ]
        transactions = fetch_all(
            """
            SELECT transaction_id, sender_account_id, sender_name, receiver_account_id,
                   receiver_name, amount, status, description, transaction_date
            FROM View_Transaction_Summary
            ORDER BY transaction_id DESC
            LIMIT 100;
            """
        )

        le_cols = ["entry_id", "transaction_id", "account_id", "entry_type", "amount", "created_at"]
        ledger_entries = fetch_all(
            """
            SELECT entry_id, transaction_id, account_id, entry_type, amount, created_at
            FROM ledger_entries
            ORDER BY entry_id DESC
            LIMIT 150;
            """
        )

        cust_cols = ["customer_id", "full_name", "email", "phone", "created_at"]
        customers = fetch_all(
            "SELECT customer_id, full_name, email, phone, created_at FROM customers ORDER BY customer_id ASC;"
        )

        loan_cols = [
            "loan_id", "customer_name", "requested_amount", "annual_income",
            "credit_score", "interest_rate", "status", "applied_at", "reviewed_at",
        ]
        loans = fetch_all(
            """
            SELECT l.loan_id, c.full_name AS customer_name, l.requested_amount, l.annual_income,
                   l.credit_score, l.interest_rate, l.status, l.applied_at, l.reviewed_at
            FROM loans l
            JOIN customers c ON l.customer_id = c.customer_id
            ORDER BY l.loan_id DESC;
            """
        )

        fraud_cols = [
            "alert_id", "transaction_id", "account_id", "customer_name",
            "receiver_account_id", "receiver_name", "transfer_amount",
            "alert_status", "transaction_status", "reason", "alert_created_at",
        ]
        fraud_alerts = fetch_all(
            """
            SELECT alert_id, transaction_id, account_id, customer_name,
                   receiver_account_id, receiver_name, transfer_amount,
                   alert_status, transaction_status, reason, alert_created_at
            FROM View_Fraud_Alerts
            ORDER BY alert_id DESC;
            """
        )

        outbox_cols = ["event_id", "event_type", "status", "retry_count", "created_at", "processed_at"]
        outbox = fetch_all(
            """
            SELECT event_id, event_type, status, retry_count, created_at, processed_at
            FROM audit_outbox
            ORDER BY created_at DESC
            LIMIT 100;
            """
        )

        return {
            "changed": True,
            "fingerprint": fp,
            "timestamp": datetime.datetime.now().isoformat(),
            "scope": "ADMIN",
            "summary": {
                "total_customers": int(kpis.get("total_customers") or 0),
                "total_accounts": int(kpis.get("total_accounts") or 0),
                "total_deposits": float(kpis.get("total_deposits") or 0),
                "total_transactions": int(kpis.get("total_transactions") or 0),
                "total_volume": float(kpis.get("total_volume") or 0),
                "total_debits": float(total_debits),
                "total_credits": float(total_credits),
                "total_ledger_entries": int(kpis.get("total_ledger_entries") or 0),
                "is_balanced": total_debits == total_credits,
                "pending_loans": int(kpis.get("pending_loans") or 0),
                "open_fraud_alerts": int(kpis.get("open_fraud_alerts") or 0),
                "delivered_outbox": int(kpis.get("delivered_outbox") or 0),
                "pending_outbox": int(kpis.get("pending_outbox") or 0),
            },
            "sheets": {
                "Accounts": {"key_field": "account_id", "columns": acc_cols, "rows": cls._serialize_rows(accounts, acc_cols)},
                "Transactions": {"key_field": "transaction_id", "columns": tx_cols, "rows": cls._serialize_rows(transactions, tx_cols)},
                "Ledger_Entries": {"key_field": "entry_id", "columns": le_cols, "rows": cls._serialize_rows(ledger_entries, le_cols)},
                "Fraud_Alerts": {"key_field": "alert_id", "columns": fraud_cols, "rows": cls._serialize_rows(fraud_alerts, fraud_cols)},
                "Loans": {"key_field": "loan_id", "columns": loan_cols, "rows": cls._serialize_rows(loans, loan_cols)},
                "Customers": {"key_field": "customer_id", "columns": cust_cols, "rows": cls._serialize_rows(customers, cust_cols)},
                "Audit_Outbox": {"key_field": "event_id", "columns": outbox_cols, "rows": cls._serialize_rows(outbox, outbox_cols)},
            },
        }

    @classmethod
    def get_customer_live_sheet_snapshot(cls, customer_id: int) -> Dict[str, Any]:
        """Return a strictly customer-isolated live multi-sheet JSON snapshot."""
        fp = cls.compute_database_fingerprint()

        acc_cols = [
            "account_id", "account_type", "balance", "currency",
            "is_frozen", "total_incoming_amount", "total_outgoing_amount", "total_transactions_count",
        ]
        accounts = fetch_all(
            """
            SELECT account_id, account_type, balance, currency, is_frozen,
                   total_incoming_amount, total_outgoing_amount, total_transactions_count
            FROM View_Account_Summary
            WHERE customer_id = %s
            ORDER BY account_id ASC;
            """,
            (customer_id,),
        )

        tx_cols = [
            "transaction_id", "sender_account_id", "sender_name", "receiver_account_id",
            "receiver_name", "amount", "status", "description", "transaction_date",
        ]
        transactions = fetch_all(
            """
            SELECT transaction_id, sender_account_id, sender_name, receiver_account_id,
                   receiver_name, amount, status, description, transaction_date
            FROM View_Transaction_Summary
            WHERE sender_customer_id = %s OR receiver_customer_id = %s
            ORDER BY transaction_id DESC
            LIMIT 100;
            """,
            (customer_id, customer_id),
        )

        le_cols = ["entry_id", "transaction_id", "account_id", "entry_type", "amount", "created_at"]
        ledger_entries = fetch_all(
            """
            SELECT le.entry_id, le.transaction_id, le.account_id, le.entry_type, le.amount, le.created_at
            FROM ledger_entries le
            JOIN accounts a ON le.account_id = a.account_id
            WHERE a.customer_id = %s
            ORDER BY le.entry_id DESC
            LIMIT 120;
            """,
            (customer_id,),
        )

        loan_cols = [
            "loan_id", "requested_amount", "annual_income", "credit_score",
            "interest_rate", "status", "applied_at", "reviewed_at",
        ]
        loans = fetch_all(
            """
            SELECT loan_id, requested_amount, annual_income, credit_score,
                   interest_rate, status, applied_at, reviewed_at
            FROM loans
            WHERE customer_id = %s
            ORDER BY loan_id DESC;
            """,
            (customer_id,),
        )

        total_balance = sum(Decimal(str(a["balance"])) for a in accounts)
        total_credits = sum(
            Decimal(str(e["amount"])) for e in ledger_entries if e["entry_type"] == "CREDIT"
        )
        total_debits = sum(
            Decimal(str(e["amount"])) for e in ledger_entries if e["entry_type"] == "DEBIT"
        )

        return {
            "changed": True,
            "fingerprint": fp,
            "timestamp": datetime.datetime.now().isoformat(),
            "scope": "CUSTOMER",
            "summary": {
                "total_accounts": len(accounts),
                "total_deposits": float(total_balance),
                "total_transactions": len(transactions),
                "total_debits": float(total_debits),
                "total_credits": float(total_credits),
                "total_ledger_entries": len(ledger_entries),
                "is_balanced": True,
                "pending_loans": sum(1 for l in loans if l["status"] == "PENDING"),
            },
            "sheets": {
                "My_Accounts": {"key_field": "account_id", "columns": acc_cols, "rows": cls._serialize_rows(accounts, acc_cols)},
                "My_Transactions": {"key_field": "transaction_id", "columns": tx_cols, "rows": cls._serialize_rows(transactions, tx_cols)},
                "My_Ledger_Entries": {"key_field": "entry_id", "columns": le_cols, "rows": cls._serialize_rows(ledger_entries, le_cols)},
                "My_Loans": {"key_field": "loan_id", "columns": loan_cols, "rows": cls._serialize_rows(loans, loan_cols)},
            },
        }

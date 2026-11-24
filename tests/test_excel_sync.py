"""
FinTrack - Live Excel Export & Real-Time Auto-Sync Tests
File: tests/test_excel_sync.py
"""

import io
import uuid
from openpyxl import load_workbook
from fastapi.testclient import TestClient

from api.main import app
from services.excel_service import DEFAULT_EXCEL_PATH, ExcelService
from workers.excel_sync_worker import ExcelSyncWorker

client = TestClient(app)


def test_full_workbook_contains_all_sheets_and_no_password_hashes():
    """Verify full workbook has all 9 sheets and strictly omits password_hash."""
    raw_bytes = ExcelService.build_full_workbook_bytes()
    wb = load_workbook(io.BytesIO(raw_bytes))

    expected_sheets = [
        "Summary",
        "Customers",
        "Users",
        "Accounts",
        "Transactions",
        "Ledger_Entries",
        "Loans",
        "Fraud_Alerts",
        "Audit_Outbox",
    ]
    assert wb.sheetnames == expected_sheets

    # Ensure password_hash is NEVER exported to Users sheet
    users_ws = wb["Users"]
    headers = [cell.value for cell in users_ws[1]]
    assert "Password Hash" not in headers
    assert "Username" in headers

    # Ensure Summary has live balanced status
    summary_ws = wb["Summary"]
    summary_values = {
        summary_ws.cell(row=r, column=1).value: summary_ws.cell(row=r, column=2).value
        for r in range(5, 17)
    }
    assert summary_values["Double-Entry Accounting Status"] == "BALANCED"


def test_live_excel_worker_detects_database_mutation(tmp_path):
    """Verify ExcelSyncWorker detects DB changes and updates the Excel file automatically."""
    test_xlsx = tmp_path / "test_live.xlsx"
    worker = ExcelSyncWorker(output_path=test_xlsx, poll_interval=1.0)

    # First run writes file
    assert worker.sync_if_changed(force=True) is True
    assert test_xlsx.exists()

    # Second run with no DB change skips redundant rewrite
    assert worker.sync_if_changed(force=False) is False

    # Execute a real transfer via API to mutate PostgreSQL
    login_res = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    tx_res = client.post(
        "/api/transfers",
        json={
            "sender_account_id": 1001,
            "receiver_account_id": 1003,
            "amount": 50.00,
            "description": "Live Excel Sync Verification Transfer",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert tx_res.status_code == 200
    tx_id = tx_res.json()["transaction_id"]

    # Worker immediately detects the change and regenerates the workbook
    assert worker.sync_if_changed(force=False) is True

    wb = load_workbook(test_xlsx)
    tx_ws = wb["Transactions"]
    tx_ids = [tx_ws.cell(row=r, column=1).value for r in range(2, tx_ws.max_row + 1)]
    assert tx_id in tx_ids


def test_excel_api_endpoints_and_rbac():
    """Verify Admin Excel export, Customer isolated Excel export, and RBAC."""
    # Customer login
    c_login = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    c_headers = {"Authorization": f"Bearer {c_login.json()['access_token']}"}

    # Customer cannot access Admin Excel export
    forbidden_res = client.get("/api/admin/export-excel", headers=c_headers)
    assert forbidden_res.status_code == 403

    # Customer can download personal isolated Excel workbook
    c_excel = client.get("/api/accounts/export-excel", headers=c_headers)
    assert c_excel.status_code == 200
    assert "spreadsheetml.sheet" in c_excel.headers["content-type"]
    c_wb = load_workbook(io.BytesIO(c_excel.content))
    assert c_wb.sheetnames == ["My_Accounts", "My_Transactions", "My_Loans"]

    # Admin login
    a_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    # Admin Excel export & status
    a_excel = client.get("/api/admin/export-excel", headers=a_headers)
    assert a_excel.status_code == 200
    assert "spreadsheetml.sheet" in a_excel.headers["content-type"]

    status_res = client.get("/api/admin/excel-status", headers=a_headers)
    assert status_res.status_code == 200
    assert status_res.json()["exists"] is True
    assert DEFAULT_EXCEL_PATH.exists()


def test_live_sheet_realtime_snapshot_and_acid_change_detection():
    """Verify live spreadsheet snapshot reflects ACID transfer changes and enforces role isolation."""
    # Admin snapshot sees all 7 bank-wide tables
    a_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}
    snap1 = client.get("/api/live-sheet/snapshot", headers=a_headers)
    assert snap1.status_code == 200
    data1 = snap1.json()
    assert data1["changed"] is True
    assert data1["scope"] == "ADMIN"
    assert data1["summary"]["is_balanced"] is True
    assert "Accounts" in data1["sheets"]
    assert "Ledger_Entries" in data1["sheets"]

    # Unchanged fingerprint short-circuits immediately
    unchanged = client.get(
        f"/api/live-sheet/snapshot?since_fingerprint={data1['fingerprint']}",
        headers=a_headers,
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["changed"] is False

    # Customer snapshot sees strictly own data (4 sheets)
    c_login = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    c_headers = {"Authorization": f"Bearer {c_login.json()['access_token']}"}
    c_snap1 = client.get("/api/live-sheet/snapshot", headers=c_headers).json()
    assert c_snap1["scope"] == "CUSTOMER"
    assert set(c_snap1["sheets"].keys()) == {
        "My_Accounts",
        "My_Transactions",
        "My_Ledger_Entries",
        "My_Loans",
    }
    bal_before = next(
        r["balance"] for r in c_snap1["sheets"]["My_Accounts"]["rows"] if r["account_id"] == 1001
    )

    # Execute a live ACID transfer of INR 100.00
    tx_res = client.post(
        "/api/transfers",
        json={
            "sender_account_id": 1001,
            "receiver_account_id": 1003,
            "amount": 100.00,
            "description": "Live Sheet ACID Change Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=c_headers,
    )
    assert tx_res.status_code == 200

    # Admin snapshot detects fingerprint change and reflects exact debit/credit + balanced ledger
    snap2 = client.get(
        f"/api/live-sheet/snapshot?since_fingerprint={data1['fingerprint']}",
        headers=a_headers,
    ).json()
    assert snap2["changed"] is True
    assert snap2["fingerprint"] != data1["fingerprint"]
    assert snap2["summary"]["is_balanced"] is True

    acc_1001_after = next(
        r["balance"] for r in snap2["sheets"]["Accounts"]["rows"] if r["account_id"] == 1001
    )
    assert round(bal_before - acc_1001_after, 2) == 100.00

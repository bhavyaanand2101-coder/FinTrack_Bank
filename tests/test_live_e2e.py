"""
FinTrack - Comprehensive End-to-End System Journey Test Suite
File: tests/test_live_e2e.py
"""

import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_01_system_health():
    """Verify backend and database connectivity."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "postgresql" in data["databases"]
    assert "mongodb" in data["databases"]


def test_02_customer_registration_and_account_creation():
    """Journey A: New customer registration, auto-login, and savings account initialization."""
    rand_suffix = str(uuid.uuid4())[:8]
    payload = {
        "full_name": f"Pooja Verma {rand_suffix}",
        "email": f"pooja.{rand_suffix}@example.com",
        "phone": f"+9198{rand_suffix[:6]}00",
        "username": f"pooja_{rand_suffix}",
        "password": "SecurePassword123!",
        "initial_deposit": 3500.00,
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == payload["username"]

    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    acc_res = client.get("/api/accounts", headers=headers)
    assert acc_res.status_code == 200
    accounts = acc_res.json()
    assert len(accounts) >= 1
    assert Decimal(str(accounts[0]["balance"])) == Decimal("3500.00")


def test_03_customer_login_and_window_statement():
    """Journey B: Customer login, accounts lookup, and Window Query running balance."""
    res_login = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    acc_res = client.get("/api/accounts", headers=headers)
    assert acc_res.status_code == 200
    accounts = acc_res.json()
    assert len(accounts) >= 2
    primary_id = accounts[0]["account_id"]

    stmt_res = client.get(f"/api/accounts/{primary_id}/statement?limit=10", headers=headers)
    assert stmt_res.status_code == 200
    stmt_data = stmt_res.json()
    assert "running_balance" in stmt_data
    assert "monthly_spending" in stmt_data
    assert len(stmt_data["running_balance"]) > 0


def test_04_routine_transfer_and_idempotency():
    """Journey C: Atomic transfer under ₹10,000 and idempotency replay protection."""
    res_login = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/accounts", headers=headers).json()
    sender_id = accounts[0]["account_id"]
    receiver_id = 1003  # Priya Sharma
    idem_key = str(uuid.uuid4())

    tx_res = client.post(
        "/api/transfers",
        json={
            "sender_account_id": sender_id,
            "receiver_account_id": receiver_id,
            "amount": 500.00,
            "description": "Routine E2E Test Transfer",
            "idempotency_key": idem_key,
        },
        headers=headers,
    )
    assert tx_res.status_code == 200
    assert tx_res.json()["status"] == "SUCCESS"

    # Replay same idempotency key
    replay_res = client.post(
        "/api/transfers",
        json={
            "sender_account_id": sender_id,
            "receiver_account_id": receiver_id,
            "amount": 500.00,
            "description": "Routine E2E Test Transfer",
            "idempotency_key": idem_key,
        },
        headers=headers,
    )
    assert replay_res.status_code == 200
    assert replay_res.json()["is_replay"] is True


def test_05_high_value_transfer_deterministic_hold():
    """Journey D: Transfer >= ₹10,000 placed deterministically on hold with zero balance movement."""
    res_login = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/accounts", headers=headers).json()
    sender_id = accounts[0]["account_id"]
    receiver_id = 1003
    bal_before = Decimal(str(accounts[0]["balance"]))

    hold_res = client.post(
        "/api/transfers",
        json={
            "sender_account_id": sender_id,
            "receiver_account_id": receiver_id,
            "amount": 15000.00,
            "description": "High Value Compliance Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert hold_res.status_code == 200
    data = hold_res.json()
    assert data["status"] == "FLAGGED"
    assert data["alert_id"] is not None

    # Check balance did not move
    acc_after = client.get(f"/api/accounts/{sender_id}", headers=headers).json()
    assert Decimal(str(acc_after["balance"])) == bal_before


def test_06_loan_calculator_and_application():
    """Journey E: Fixed-rule loan eligibility preview and customer application."""
    res_login = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    calc_res = client.post(
        "/api/loans/calculate",
        json={
            "annual_income": 900000.00,
            "requested_amount": 200000.00,
            "credit_score": 770,
        },
        headers=headers,
    )
    assert calc_res.status_code == 200
    assert calc_res.json()["is_eligible"] is True

    app_res = client.post(
        "/api/loans",
        json={
            "annual_income": 900000.00,
            "requested_amount": 200000.00,
            "credit_score": 770,
        },
        headers=headers,
    )
    assert app_res.status_code == 201
    assert app_res.json()["status"] == "PENDING"


def test_07_admin_fraud_approval_and_double_decision_prevention():
    """Journey F: Admin adjudicates flagged transfer and blocks duplicate decisions."""
    # 1. Arun initiates flagged transfer
    res_arun = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    arun_token = res_arun.json()["access_token"]
    arun_headers = {"Authorization": f"Bearer {arun_token}"}
    accounts = client.get("/api/accounts", headers=arun_headers).json()
    sender_id = accounts[0]["account_id"]

    hold = client.post(
        "/api/transfers",
        json={
            "sender_account_id": sender_id,
            "receiver_account_id": 1003,
            "amount": 10000.00,
            "description": "Admin review test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=arun_headers,
    ).json()
    alert_id = hold["alert_id"]

    # 2. Admin logs in and approves
    res_admin = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    admin_token = res_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    app_res = client.patch(
        f"/api/admin/fraud-alerts/{alert_id}/approve",
        json={"notes": "Approved by E2E test suite"},
        headers=admin_headers,
    )
    assert app_res.status_code == 200

    # 3. Duplicate decision is rejected
    dup_res = client.patch(
        f"/api/admin/fraud-alerts/{alert_id}/approve",
        json={"notes": "Duplicate approval"},
        headers=admin_headers,
    )
    assert dup_res.status_code == 400


def test_08_admin_account_freeze_unfreeze():
    """Journey G: Admin freezes account, blocks transfers, and unfreezes."""
    res_admin = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    admin_headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

    # Freeze Account 1005 (Rohit Verma)
    frz_res = client.patch(
        "/api/admin/accounts/1005/freeze",
        json={"freeze": True},
        headers=admin_headers,
    )
    assert frz_res.status_code == 200

    # Attempt transfer while frozen
    res_rohit = client.post(
        "/api/auth/login",
        json={"username": "rohit_verma", "password": "Customer123!"},
    )
    rohit_headers = {"Authorization": f"Bearer {res_rohit.json()['access_token']}"}

    tx_blocked = client.post(
        "/api/transfers",
        json={
            "sender_account_id": 1005,
            "receiver_account_id": 1001,
            "amount": 100.00,
            "description": "Should fail frozen",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=rohit_headers,
    )
    assert tx_blocked.status_code == 400

    # Unfreeze
    unfrz_res = client.patch(
        "/api/admin/accounts/1005/freeze",
        json={"freeze": False},
        headers=admin_headers,
    )
    assert unfrz_res.status_code == 200


def test_09_admin_advanced_sql_reports():
    """Journey I: Execute all 5 Advanced DBMS SQL queries."""
    res_admin = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    admin_headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

    reports_res = client.get("/api/admin/reports", headers=admin_headers)
    assert reports_res.status_code == 200
    data = reports_res.json()
    assert "monthly_volume" in data
    assert "top_customers" in data
    assert "dormant_accounts" in data
    assert "account_summaries" in data


def test_10_idor_customer_isolation():
    """Journey K: Verify customer cannot access another customer's account data."""
    # Register Customer A
    rand_a = str(uuid.uuid4())[:8]
    reg_a = client.post(
        "/api/auth/register",
        json={
            "full_name": f"User A {rand_a}",
            "email": f"a.{rand_a}@example.com",
            "phone": f"+9199{rand_a[:6]}00",
            "username": f"user_a_{rand_a}",
            "password": "Password123!",
            "initial_deposit": 1000.00,
        },
    ).json()
    headers_a = {"Authorization": f"Bearer {reg_a['access_token']}"}

    # Customer A tries to access Arun Kumar's Account 1001
    idor_res = client.get("/api/accounts/1001", headers=headers_a)
    assert idor_res.status_code in (403, 404)


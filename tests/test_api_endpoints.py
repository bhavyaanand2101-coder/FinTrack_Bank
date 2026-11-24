"""
FinTrack - FastAPI Endpoints Integration & Security Tests
File: tests/test_api_endpoints.py
"""

from decimal import Decimal
import uuid
import pytest
from starlette.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "postgresql" in data["databases"]


def test_auth_login_customer_and_admin():
    # 1. Customer login
    res_cust = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    assert res_cust.status_code == 200
    cust_data = res_cust.json()
    assert "access_token" in cust_data
    assert cust_data["user"]["role"] == "CUSTOMER"
    assert cust_data["user"]["customer_id"] == 1

    # 2. Admin login
    res_admin = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    assert res_admin.status_code == 200
    admin_data = res_admin.json()
    assert "access_token" in admin_data
    assert admin_data["user"]["role"] == "ADMIN"

    # 3. Invalid password
    res_bad = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "WrongPassword!"},
    )
    assert res_bad.status_code == 401


def test_auth_me_profile():
    # Login to obtain token
    res = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token = res.json()["access_token"]

    # Request /api/auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "arun_kumar"
    assert me_data["customer_id"] == 1


def test_accounts_isolation_and_statement():
    # Login as Customer 1 (arun_kumar)
    res1 = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token1 = res1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Fetch accounts - Customer 1 should only see accounts 1001, 1002
    acc_res = client.get("/api/accounts", headers=headers1)
    assert acc_res.status_code == 200
    accounts = acc_res.json()
    assert len(accounts) >= 1
    for a in accounts:
        assert a["customer_id"] == 1

    # Statement for own account 1001
    stmt_res = client.get("/api/accounts/1001/statement", headers=headers1)
    assert stmt_res.status_code == 200
    stmt = stmt_res.json()
    assert "running_balance" in stmt
    assert "monthly_spending" in stmt

    # IDOR Test: Customer 1 tries to access Customer 2's account 1003
    idor_res = client.get("/api/accounts/1003/statement", headers=headers1)
    assert idor_res.status_code == 403


def test_transfer_execution_and_idempotency():
    res1 = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token1 = res1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    idem_key = str(uuid.uuid4())

    # Execute valid transfer below threshold (₹250.00)
    transfer_payload = {
        "sender_account_id": 1001,
        "receiver_account_id": 1003,
        "amount": "250.00",
        "description": "API Transfer Test",
        "idempotency_key": idem_key,
    }
    tx_res = client.post("/api/transfers", json=transfer_payload, headers=headers1)
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert tx_data["status"] == "SUCCESS"
    assert tx_data["is_replay"] is False

    # Replay with same idempotency key must not double spend
    replay_res = client.post("/api/transfers", json=transfer_payload, headers=headers1)
    assert replay_res.status_code == 200
    replay_data = replay_res.json()
    assert replay_data["is_replay"] is True


def test_transfer_flagged_deterministic_threshold():
    res1 = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    token1 = res1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Transfer >= ₹10,000 must be FLAGGED
    transfer_payload = {
        "sender_account_id": 1001,
        "receiver_account_id": 1003,
        "amount": "15000.00",
        "description": "High Value API Transfer",
        "idempotency_key": str(uuid.uuid4()),
    }
    tx_res = client.post("/api/transfers", json=transfer_payload, headers=headers1)
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert tx_data["status"] == "FLAGGED"
    assert tx_data["alert_id"] is not None


def test_loan_calculation_and_application():
    # Customer login
    res = client.post(
        "/api/auth/login",
        json={"username": "priya_sharma", "password": "Customer123!"},
    )
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Calculate eligibility
    calc_res = client.post(
        "/api/loans/calculate",
        json={"annual_income": "800000.00", "requested_amount": "200000.00", "credit_score": 800},
        headers=headers,
    )
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["is_eligible"] is True
    assert calc_data["status"] == "PRE-APPROVED"

    # Submit application
    apply_res = client.post(
        "/api/loans",
        json={"annual_income": "800000.00", "requested_amount": "200000.00", "credit_score": 800},
        headers=headers,
    )
    assert apply_res.status_code == 201
    apply_data = apply_res.json()
    assert apply_data["status"] == "PENDING"


def test_admin_rbac_and_operations():
    # 1. Customer denied access to admin endpoints
    res_cust = client.post(
        "/api/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
    )
    cust_token = res_cust.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    admin_dash_res = client.get("/api/admin/dashboard", headers=cust_headers)
    assert admin_dash_res.status_code == 403

    # 2. Admin access granted
    res_admin = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
    )
    admin_token = res_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Dashboard KPIs
    kpi_res = client.get("/api/admin/dashboard", headers=admin_headers)
    assert kpi_res.status_code == 200
    kpis = kpi_res.json()
    assert kpis["total_customers"] >= 10
    assert kpis["total_accounts"] >= 16

    # Advanced Reports
    rep_res = client.get("/api/admin/reports", headers=admin_headers)
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert "top_customers" in rep_data
    assert "dormant_accounts" in rep_data
    assert "monthly_volume" in rep_data

    # Customers list with accounts
    cust_list_res = client.get("/api/admin/customers", headers=admin_headers)
    assert cust_list_res.status_code == 200
    assert len(cust_list_res.json()) >= 10


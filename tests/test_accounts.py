"""
FinTrack - Account Management and Authorization Unit Tests
File: tests/test_accounts.py
"""

from decimal import Decimal
import pytest

from database_layer.postgres import DatabaseError, NotFoundError, execute_update
from services.account_service import account_service


def test_customer_sees_only_own_accounts():
    # Customer 1 (Arun Kumar) owns 1001 and 1002
    accs = account_service.get_customer_accounts(customer_id=1)
    acc_ids = [a["account_id"] for a in accs]
    assert 1001 in acc_ids
    assert 1002 in acc_ids
    # Should not see Customer 2's accounts (1003)
    assert 1003 not in acc_ids


def test_cross_customer_access_prevention():
    # Attempting to fetch Customer 2's account (1003) as Customer 1 should raise Unauthorized
    with pytest.raises(DatabaseError, match="Unauthorized"):
        account_service.get_account_by_id(account_id=1003, customer_id=1)


def test_account_details_and_balance_retrieval():
    acc = account_service.get_account_by_id(account_id=1001, customer_id=1)
    assert acc["account_id"] == 1001
    assert acc["customer_id"] == 1
    assert acc["currency"] == "INR"
    assert isinstance(acc["balance"], Decimal)
    assert acc["balance"] >= Decimal("0.00")


def test_frozen_account_detection():
    # Freeze account 1005 temporarily
    execute_update("UPDATE accounts SET is_frozen = TRUE WHERE account_id = 1005;")
    try:
        acc = account_service.get_account_by_id(1005)
        assert acc["is_frozen"] is True
    finally:
        execute_update("UPDATE accounts SET is_frozen = FALSE WHERE account_id = 1005;")


def test_running_balance_window_query():
    # Account 1001 has historical ledger entries
    running_entries = account_service.get_running_balance(account_id=1001, limit=10)
    assert len(running_entries) > 0
    first_entry = running_entries[0]
    assert "running_balance" in first_entry
    assert "amount" in first_entry
    assert "entry_type" in first_entry


def test_monthly_spending_analysis_cte():
    # Account 1001 has outgoing transactions
    monthly_data = account_service.get_monthly_spending_analysis(account_id=1001)
    assert isinstance(monthly_data, list)
    if monthly_data:
        month = monthly_data[0]
        assert "month_label" in month
        assert "total_monthly_outgoing" in month
        assert "transfer_count" in month


def test_account_summary_metrics_view():
    summary = account_service.get_account_summary_metrics(1001)
    assert summary["account_id"] == 1001
    assert "total_incoming_amount" in summary
    assert "total_outgoing_amount" in summary
    assert "total_transactions_count" in summary


def test_toggle_account_freeze():
    # Freeze account 1002
    account_service.toggle_account_freeze(account_id=1002, freeze=True, admin_user_id=1)
    acc = account_service.get_account_by_id(1002)
    assert acc["is_frozen"] is True

    # Unfreeze account 1002
    account_service.toggle_account_freeze(account_id=1002, freeze=False, admin_user_id=1)
    acc_unfrozen = account_service.get_account_by_id(1002)
    assert acc_unfrozen["is_frozen"] is False


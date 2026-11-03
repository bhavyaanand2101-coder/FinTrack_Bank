"""
FinTrack - Financial Transfer Engine Unit Tests
File: tests/test_transfers.py
"""

from decimal import Decimal
import uuid
import pytest

from database_layer.postgres import (
    AccountFrozenError,
    DatabaseError,
    InsufficientFundsError,
    NotFoundError,
    execute_scalar,
    execute_update,
    fetch_all,
    fetch_one,
)
from services.account_service import account_service
from services.fraud_service import fraud_service
from services.transfer_service import transfer_service


def test_successful_transfer_and_balanced_ledger():
    # Customer 1 transfers 500.00 INR from 1001 to 1003 (Priya Sharma)
    sender_before = account_service.get_account_by_id(1001)["balance"]
    receiver_before = account_service.get_account_by_id(1003)["balance"]

    transfer_amount = Decimal("500.00")
    idem_key = str(uuid.uuid4())

    res = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=transfer_amount,
        description="Test clean transfer",
        idempotency_key=idem_key,
    )

    assert res["status"] == "SUCCESS"
    tx_id = res["transaction_id"]

    sender_after = account_service.get_account_by_id(1001)["balance"]
    receiver_after = account_service.get_account_by_id(1003)["balance"]

    assert sender_after == sender_before - transfer_amount
    assert receiver_after == receiver_before + transfer_amount

    # Verify double-entry ledger balance
    ledgers = fetch_all("SELECT entry_type, amount, account_id FROM ledger_entries WHERE transaction_id = %s;", (tx_id,))
    assert len(ledgers) == 2

    debits = [l for l in ledgers if l["entry_type"] == "DEBIT"]
    credits = [l for l in ledgers if l["entry_type"] == "CREDIT"]

    assert len(debits) == 1 and debits[0]["account_id"] == 1001
    assert len(credits) == 1 and credits[0]["account_id"] == 1003
    assert debits[0]["amount"] == credits[0]["amount"] == transfer_amount


def test_insufficient_balance_rejection():
    # Attempt to transfer 1,000,000 INR from 1001 (balance is ~74k)
    sender_before = account_service.get_account_by_id(1001)["balance"]
    receiver_before = account_service.get_account_by_id(1003)["balance"]

    with pytest.raises(InsufficientFundsError):
        transfer_service.execute_transfer(
            authenticated_customer_id=1,
            sender_account_id=1001,
            receiver_account_id=1003,
            amount=Decimal("1000000.00"),
            description="Attempted overdraft",
        )

    # Balances must remain strictly unchanged
    assert account_service.get_account_by_id(1001)["balance"] == sender_before
    assert account_service.get_account_by_id(1003)["balance"] == receiver_before


def test_invalid_receiver_rejection():
    with pytest.raises(NotFoundError, match="Receiver account .* does not exist"):
        transfer_service.execute_transfer(
            authenticated_customer_id=1,
            sender_account_id=1001,
            receiver_account_id=999999,
            amount=Decimal("100.00"),
        )


def test_frozen_sender_account():
    execute_update("UPDATE accounts SET is_frozen = TRUE WHERE account_id = 1001;")
    try:
        with pytest.raises(AccountFrozenError, match="Sender account .* is frozen"):
            transfer_service.execute_transfer(
                authenticated_customer_id=1,
                sender_account_id=1001,
                receiver_account_id=1003,
                amount=Decimal("100.00"),
            )
    finally:
        execute_update("UPDATE accounts SET is_frozen = FALSE WHERE account_id = 1001;")


def test_frozen_receiver_account():
    execute_update("UPDATE accounts SET is_frozen = TRUE WHERE account_id = 1003;")
    try:
        with pytest.raises(AccountFrozenError, match="Receiver account .* is frozen"):
            transfer_service.execute_transfer(
                authenticated_customer_id=1,
                sender_account_id=1001,
                receiver_account_id=1003,
                amount=Decimal("100.00"),
            )
    finally:
        execute_update("UPDATE accounts SET is_frozen = FALSE WHERE account_id = 1003;")


def test_negative_and_zero_amount():
    with pytest.raises(ValueError, match="strictly greater than zero"):
        transfer_service.execute_transfer(1, 1001, 1003, Decimal("-50.00"))

    with pytest.raises(ValueError, match="strictly greater than zero"):
        transfer_service.execute_transfer(1, 1001, 1003, Decimal("0.00"))


def test_same_sender_and_receiver():
    with pytest.raises(ValueError, match="must be different"):
        transfer_service.execute_transfer(1, 1001, 1001, Decimal("100.00"))


def test_idempotent_duplicate_request():
    shared_key = str(uuid.uuid4())
    # First execution
    res1 = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=Decimal("200.00"),
        idempotency_key=shared_key,
    )
    assert res1["status"] == "SUCCESS"

    # Second execution with exact same idempotency key
    res2 = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=Decimal("200.00"),
        idempotency_key=shared_key,
    )
    # Must detect replay and return original transaction without deducting funds again
    assert res2.get("is_replay") is True
    assert res2["transaction_id"] == res1["transaction_id"]


def test_flagged_transfer_without_money_movement():
    # Ensure sufficient balance on Account 1001 for high-value transfer testing
    execute_update("UPDATE accounts SET balance = 50000.00 WHERE account_id = 1001;")
    sender_before = account_service.get_account_by_id(1001)["balance"]
    receiver_before = account_service.get_account_by_id(1003)["balance"]

    large_amount = Decimal("12500.00")
    res = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=large_amount,
        description="High value purchase deposit",
    )

    assert res["status"] == "FLAGGED"
    tx_id = res["transaction_id"]
    alert_id = res["alert_id"]

    # Verify balances remained completely unchanged
    assert account_service.get_account_by_id(1001)["balance"] == sender_before
    assert account_service.get_account_by_id(1003)["balance"] == receiver_before

    # Verify zero ledger entries were written for FLAGGED transfer
    ledger_count = execute_scalar("SELECT COUNT(*) FROM ledger_entries WHERE transaction_id = %s;", (tx_id,))
    assert ledger_count == 0

    # Test Admin Approval of this Flagged Transfer
    approve_res = fraud_service.review_flagged_transfer(
        alert_id=alert_id,
        admin_user_id=1,
        decision="APPROVE",
        admin_notes="Verified by compliance team.",
    )
    assert approve_res["status"] == "APPROVED"

    # Now verify money was atomically moved after approval!
    assert account_service.get_account_by_id(1001)["balance"] == sender_before - large_amount
    assert account_service.get_account_by_id(1003)["balance"] == receiver_before + large_amount

    # And exactly 2 balanced ledger entries now exist!
    ledger_count_after = execute_scalar("SELECT COUNT(*) FROM ledger_entries WHERE transaction_id = %s;", (tx_id,))
    assert ledger_count_after == 2


def test_flagged_transfer_rejection():
    # Ensure sufficient balance on Account 1001 for high-value transfer testing
    execute_update("UPDATE accounts SET balance = 50000.00 WHERE account_id = 1001;")
    res = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=Decimal("15000.00"),
        description="Suspicious overseas wire",
    )
    assert res["status"] == "FLAGGED"
    alert_id = res["alert_id"]
    tx_id = res["transaction_id"]

    sender_before = account_service.get_account_by_id(1001)["balance"]

    # Admin Rejects
    rej_res = fraud_service.review_flagged_transfer(
        alert_id=alert_id,
        admin_user_id=1,
        decision="REJECT",
        admin_notes="Suspicious IP address origin.",
    )
    assert rej_res["status"] == "REJECTED"

    # Balance remains unchanged
    assert account_service.get_account_by_id(1001)["balance"] == sender_before

    # Transaction status updated to FAILED
    tx = fetch_one("SELECT status FROM transactions WHERE transaction_id = %s;", (tx_id,))
    assert tx["status"] == "FAILED"

"""
FinTrack - Deterministic Rule-Based Fraud Detection Unit Tests
File: tests/test_fraud.py
"""

from decimal import Decimal
import pytest

from config.settings import settings
from services.transfer_service import transfer_service


def test_rule_based_fraud_threshold():
    """Transfers below threshold are cleared; transfers at or above threshold are flagged."""
    assert Decimal("9999.00") < settings.FRAUD_THRESHOLD
    assert Decimal("10000.00") >= settings.FRAUD_THRESHOLD
    assert Decimal("50000.00") >= settings.FRAUD_THRESHOLD


def test_deterministic_fraud_flagging_without_money_movement(db_conn):
    """
    Ensure a transfer of INR 10,000 or more is automatically flagged
    under strict deterministic rules with zero balance changes.
    """
    with db_conn.cursor() as cur:
        # Guarantee sender account 1001 has adequate balance for the transfer
        cur.execute("UPDATE accounts SET balance = 50000.00 WHERE account_id = 1001;")
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("SELECT balance FROM accounts WHERE account_id = 1001;")
        initial_balance = cur.fetchone()[0]

    result = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=Decimal("12000.00"),
        description="High-value transfer test",
    )
    assert result["status"] == "FLAGGED"
    assert result["amount"] == Decimal("12000.00")
    assert "flagged" in result["message"].lower()

    # Verify balance was untouched
    with db_conn.cursor() as cur:
        cur.execute("SELECT balance FROM accounts WHERE account_id = 1001;")
        final_balance = cur.fetchone()[0]
    assert final_balance == initial_balance

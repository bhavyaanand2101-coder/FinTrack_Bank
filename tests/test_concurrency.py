"""
FinTrack - Database Concurrency & Deadlock Prevention Tests
File: tests/test_concurrency.py
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import time
import pytest

from database_layer.postgres import execute_update, fetch_one
from services.account_service import account_service
from services.transfer_service import transfer_service


def test_concurrent_transfers_prevent_double_spending():
    """
    Test Race Condition Protection:
    Account starts with exactly INR 3,000.00.
    10 concurrent threads simultaneously try to transfer INR 1,000.00 each.
    Expected: Exactly 3 succeed, exactly 7 fail with InsufficientFunds.
    Balance must end at exactly INR 0.00 (NO overdrafts).
    """
    # Set known balance on Account 1002 (Checking, Customer 1)
    execute_update("UPDATE accounts SET balance = 3000.00 WHERE account_id = 1002;")
    target_account = 1004  # Checking, Customer 2

    success_count = 0
    failure_count = 0

    def attempt_transfer(idx):
        return transfer_service.execute_transfer(
            authenticated_customer_id=1,
            sender_account_id=1002,
            receiver_account_id=target_account,
            amount=Decimal("1000.00"),
            description=f"Concurrency race test #{idx}",
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_transfer, i) for i in range(10)]
        for f in as_completed(futures):
            try:
                res = f.result()
                if res["status"] == "SUCCESS":
                    success_count += 1
            except Exception:
                failure_count += 1

    final_balance = account_service.get_account_by_id(1002)["balance"]

    assert success_count == 3
    assert failure_count == 7
    assert final_balance == Decimal("0.00")


def test_opposite_direction_concurrent_transfers_no_deadlock():
    """
    Test Deadlock Avoidance:
    Account A (1001) -> B (1003) and Account B (1003) -> A (1001) executed concurrently.
    Because both acquire row locks in ASCENDING account_id order (1001 then 1003),
    no circular wait / deadlock condition can occur.
    """
    execute_update("UPDATE accounts SET balance = 10000.00 WHERE account_id = 1001;")
    execute_update("UPDATE accounts SET balance = 10000.00 WHERE account_id = 1003;")

    def transfer_a_to_b():
        return transfer_service.execute_transfer(
            authenticated_customer_id=1,
            sender_account_id=1001,
            receiver_account_id=1003,
            amount=Decimal("100.00"),
            description="A to B",
        )

    def transfer_b_to_a():
        return transfer_service.execute_transfer(
            authenticated_customer_id=2,
            sender_account_id=1003,
            receiver_account_id=1001,
            amount=Decimal("150.00"),
            description="B to A",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(transfer_a_to_b)
        f2 = executor.submit(transfer_b_to_a)
        res1 = f1.result()
        res2 = f2.result()

    assert res1["status"] == "SUCCESS"
    assert res2["status"] == "SUCCESS"


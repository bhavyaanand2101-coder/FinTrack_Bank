"""
FinTrack - Database Triggers, Constraints & Views Unit Tests
File: tests/test_database.py
"""

from decimal import Decimal
import uuid
import pytest

from database_layer.postgres import (
    DatabaseError,
    IntegrityError,
    execute_scalar,
    execute_update,
    fetch_all,
    fetch_one,
)


def test_schema_table_existence():
    tables = [
        "customers", "users", "accounts", "transactions", 
        "ledger_entries", "loans", "fraud_alerts", "audit_outbox"
    ]
    for tbl in tables:
        count = execute_scalar("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s;", (tbl,))
        assert count == 1, f"Table {tbl} missing from schema."


def test_overdraft_prevention_trigger():
    # Trigger 1: Negative balance update must be rejected by PostgreSQL trigger
    with pytest.raises(DatabaseError, match="balance"):
        execute_update("UPDATE accounts SET balance = -500.00 WHERE account_id = 1001;")


def test_large_transfer_flagging_trigger():
    # Trigger 2: Any transfer inserted with amount >= 10,000 must be modified to FLAGGED by trigger
    idem = str(uuid.uuid4())
    execute_update(
        """
        INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description)
        VALUES (1001, 1003, 15000.00, 'PENDING', %s, 'Direct trigger test');
        """,
        (idem,),
    )
    tx = fetch_one("SELECT status FROM transactions WHERE idempotency_key = %s;", (idem,))
    assert tx["status"] == "FLAGGED"


def test_ledger_immutability_trigger():
    # Trigger 3: Committed ledger records cannot be deleted or updated
    first_entry_id = execute_scalar("SELECT entry_id FROM ledger_entries ORDER BY entry_id ASC LIMIT 1;")
    assert first_entry_id is not None

    with pytest.raises(DatabaseError, match="strictly immutable"):
        execute_update("UPDATE ledger_entries SET amount = 9999.00 WHERE entry_id = %s;", (first_entry_id,))

    with pytest.raises(DatabaseError, match="strictly immutable"):
        execute_update("DELETE FROM ledger_entries WHERE entry_id = %s;", (first_entry_id,))


def test_views_return_valid_data():
    v1 = fetch_all("SELECT * FROM View_Loan_Eligibility LIMIT 5;")
    assert len(v1) > 0
    assert "eligibility_status" in v1[0]
    assert "suggested_interest_rate" in v1[0]

    v2 = fetch_all("SELECT * FROM View_Account_Summary LIMIT 5;")
    assert len(v2) > 0
    assert "total_incoming_amount" in v2[0]

    v3 = fetch_all("SELECT * FROM View_Transaction_Summary LIMIT 5;")
    assert len(v3) > 0
    assert "sender_name" in v3[0]

    v4 = fetch_all("SELECT * FROM View_Fraud_Alerts LIMIT 5;")
    assert len(v4) > 0
    assert "risk_score" in v4[0]


def test_foreign_key_and_check_constraints():
    # Invalid customer reference
    with pytest.raises(IntegrityError):
        execute_update(
            """
            INSERT INTO accounts (customer_id, account_type, balance)
            VALUES (999999, 'SAVINGS', 100.00);
            """
        )

    # Invalid account_type CHECK constraint
    with pytest.raises(IntegrityError):
        execute_update(
            """
            INSERT INTO accounts (customer_id, account_type, balance)
            VALUES (1, 'INVALID_TYPE', 100.00);
            """
        )


def test_row_level_security_enforcement(db_conn):
    from database_layer.postgres import set_rls_context

    with db_conn.cursor() as cur:
        # Switch to non-superuser application role to enforce RLS
        cur.execute("SET ROLE fintrack_app;")
        try:
            # 1. Enforce Customer 1 RLS context
            set_rls_context(db_conn, customer_id=1, role="CUSTOMER")

            # Querying accounts for Customer 2 under Customer 1 RLS must return empty set
            cur.execute("SELECT account_id FROM accounts WHERE customer_id = 2;")
            rows = cur.fetchall()
            assert len(rows) == 0, "RLS failed to block cross-customer account query"

            # Querying accounts for Customer 1 returns Customer 1's own accounts
            cur.execute("SELECT account_id FROM accounts WHERE customer_id = 1;")
            own_rows = cur.fetchall()
            assert len(own_rows) >= 1

            # 2. Switch to ADMIN RLS context
            set_rls_context(db_conn, customer_id=None, role="ADMIN")
            cur.execute("SELECT account_id FROM accounts WHERE customer_id = 2;")
            admin_rows = cur.fetchall()
            assert len(admin_rows) >= 1, "Admin should be able to see all accounts"
        finally:
            cur.execute("RESET ROLE;")


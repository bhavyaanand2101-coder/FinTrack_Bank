"""Initial banking schema with triggers, views, and indexes

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-03 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2. Customers
    op.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id SERIAL PRIMARY KEY,
        full_name VARCHAR(150) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        phone VARCHAR(20) UNIQUE NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Users
    op.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id SERIAL PRIMARY KEY,
        customer_id INTEGER REFERENCES customers(customer_id) ON DELETE SET NULL,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'CUSTOMER' CHECK (role IN ('CUSTOMER', 'ADMIN')),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Accounts
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        account_id BIGSERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
        account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('SAVINGS', 'CHECKING')),
        balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
        currency VARCHAR(3) NOT NULL DEFAULT 'INR',
        is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT chk_positive_balance CHECK (balance >= 0.00)
    );
    """)

    # 5. Transactions
    op.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id BIGSERIAL PRIMARY KEY,
        sender_account_id BIGINT NOT NULL REFERENCES accounts(account_id),
        receiver_account_id BIGINT NOT NULL REFERENCES accounts(account_id),
        amount NUMERIC(15, 2) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED', 'FLAGGED')),
        idempotency_key UUID UNIQUE NOT NULL,
        description TEXT,
        transaction_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT chk_positive_amount CHECK (amount > 0.00),
        CONSTRAINT chk_distinct_accounts CHECK (sender_account_id <> receiver_account_id)
    );
    """)

    # 6. Ledger Entries
    op.execute("""
    CREATE TABLE IF NOT EXISTS ledger_entries (
        entry_id BIGSERIAL PRIMARY KEY,
        transaction_id BIGINT NOT NULL REFERENCES transactions(transaction_id) ON DELETE RESTRICT,
        account_id BIGINT NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
        entry_type VARCHAR(10) NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
        amount NUMERIC(15, 2) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT chk_ledger_amount CHECK (amount > 0.00)
    );
    """)

    # 7. Loans
    op.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        loan_id BIGSERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
        requested_amount NUMERIC(15, 2) NOT NULL CHECK (requested_amount > 0.00),
        annual_income NUMERIC(15, 2) NOT NULL CHECK (annual_income > 0.00),
        credit_score INTEGER NOT NULL CHECK (credit_score BETWEEN 300 AND 900),
        interest_rate NUMERIC(5, 2) NOT NULL CHECK (interest_rate >= 0.00),
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMPTZ,
        reviewed_by INTEGER REFERENCES users(user_id)
    );
    """)

    # 8. Fraud Alerts
    op.execute("""
    CREATE TABLE IF NOT EXISTS fraud_alerts (
        alert_id BIGSERIAL PRIMARY KEY,
        transaction_id BIGINT NOT NULL REFERENCES transactions(transaction_id) ON DELETE CASCADE,
        account_id BIGINT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
        risk_score NUMERIC(10, 4) NOT NULL,
        reason TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'APPROVED', 'REJECTED')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMPTZ
    );
    """)

    # 9. Audit Outbox
    op.execute("""
    CREATE TABLE IF NOT EXISTS audit_outbox (
        event_id UUID PRIMARY KEY,
        event_type VARCHAR(100) NOT NULL,
        payload JSONB NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'DELIVERED', 'FAILED')),
        retry_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMPTZ,
        last_error TEXT
    );
    """)

    # 10. Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounts_customer_id ON accounts(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender_account_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver_account_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_account_created ON ledger_entries(account_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_transaction ON ledger_entries(transaction_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_loans_customer_id ON loans(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fraud_alerts_status ON fraud_alerts(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_outbox_pending ON audit_outbox(status, created_at) WHERE status IN ('PENDING', 'PROCESSING');")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trans_sender_date ON transactions(sender_account_id, transaction_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trans_receiver_date ON transactions(receiver_account_id, transaction_date DESC);")

    # 11. Triggers
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_overdraft()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.balance < 0.00 THEN
            RAISE EXCEPTION 'Negative balance violation: account % has insufficient funds', NEW.account_id;
        END IF;
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_prevent_overdraft ON accounts;
    CREATE TRIGGER trg_prevent_overdraft
    BEFORE UPDATE ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION fn_prevent_overdraft();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION fn_detect_large_transfer()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.amount >= 10000.00 AND NEW.status IN ('PENDING', 'SUCCESS') THEN
            NEW.status := 'FLAGGED';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_detect_large_transfer ON transactions;
    CREATE TRIGGER trg_detect_large_transfer
    BEFORE INSERT ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION fn_detect_large_transfer();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION fn_enforce_ledger_immutability()
    RETURNS TRIGGER AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Ledger entries are strictly immutable. Deletion of entry % is prohibited.', OLD.entry_id;
        ELSIF TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'Ledger entries are strictly immutable. Updating entry % is prohibited.', OLD.entry_id;
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_enforce_ledger_immutability ON ledger_entries;
    CREATE TRIGGER trg_enforce_ledger_immutability
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW
    EXECUTE FUNCTION fn_enforce_ledger_immutability();
    """)

    # 12. Views
    op.execute("""
    CREATE OR REPLACE VIEW View_Loan_Eligibility AS
    SELECT 
        c.customer_id,
        c.full_name AS customer_name,
        c.email,
        COALESCE(l.annual_income, 0.00) AS latest_annual_income,
        COALESCE(l.credit_score, 0) AS latest_credit_score,
        ROUND(COALESCE(l.annual_income, 0.00) * 0.50, 2) AS max_eligible_loan_amount,
        CASE 
            WHEN COALESCE(l.credit_score, 0) >= 750 AND COALESCE(l.annual_income, 0.00) >= 300000 THEN 'PRE-APPROVED'
            WHEN COALESCE(l.credit_score, 0) >= 650 AND COALESCE(l.annual_income, 0.00) >= 200000 THEN 'ELIGIBLE'
            ELSE 'INELIGIBLE'
        END AS eligibility_status,
        CASE
            WHEN COALESCE(l.credit_score, 0) >= 800 THEN 7.50
            WHEN COALESCE(l.credit_score, 0) >= 750 THEN 8.75
            WHEN COALESCE(l.credit_score, 0) >= 700 THEN 10.50
            WHEN COALESCE(l.credit_score, 0) >= 650 THEN 12.00
            ELSE 15.00
        END AS suggested_interest_rate
    FROM customers c
    LEFT JOIN LATERAL (
        SELECT annual_income, credit_score
        FROM loans
        WHERE customer_id = c.customer_id
        ORDER BY applied_at DESC
        LIMIT 1
    ) l ON TRUE;
    """)

    op.execute("""
    CREATE OR REPLACE VIEW View_Account_Summary AS
    SELECT 
        a.account_id,
        a.customer_id,
        c.full_name AS customer_name,
        c.email AS customer_email,
        a.account_type,
        a.balance,
        a.currency,
        a.is_frozen,
        a.created_at,
        COALESCE(credits.total_credited, 0.00) AS total_incoming_amount,
        COALESCE(debits.total_debited, 0.00) AS total_outgoing_amount,
        (COALESCE(credits.tx_count, 0) + COALESCE(debits.tx_count, 0)) AS total_transactions_count
    FROM accounts a
    JOIN customers c ON a.customer_id = c.customer_id
    LEFT JOIN (
        SELECT account_id, SUM(amount) AS total_credited, COUNT(*) AS tx_count
        FROM ledger_entries
        WHERE entry_type = 'CREDIT'
        GROUP BY account_id
    ) credits ON a.account_id = credits.account_id
    LEFT JOIN (
        SELECT account_id, SUM(amount) AS total_debited, COUNT(*) AS tx_count
        FROM ledger_entries
        WHERE entry_type = 'DEBIT'
        GROUP BY account_id
    ) debits ON a.account_id = debits.account_id;
    """)

    op.execute("""
    CREATE OR REPLACE VIEW View_Transaction_Summary AS
    SELECT 
        t.transaction_id,
        t.idempotency_key,
        t.sender_account_id,
        sc.full_name AS sender_name,
        sc.customer_id AS sender_customer_id,
        t.receiver_account_id,
        rc.full_name AS receiver_name,
        rc.customer_id AS receiver_customer_id,
        t.amount,
        sa.currency,
        t.status,
        t.description,
        t.transaction_date
    FROM transactions t
    JOIN accounts sa ON t.sender_account_id = sa.account_id
    JOIN customers sc ON sa.customer_id = sc.customer_id
    JOIN accounts ra ON t.receiver_account_id = ra.account_id
    JOIN customers rc ON ra.customer_id = rc.customer_id;
    """)

    op.execute("""
    CREATE OR REPLACE VIEW View_Fraud_Alerts AS
    SELECT 
        fa.alert_id,
        fa.transaction_id,
        fa.account_id,
        c.customer_id,
        c.full_name AS customer_name,
        c.email AS customer_email,
        t.amount AS transfer_amount,
        t.receiver_account_id,
        rc.full_name AS receiver_name,
        fa.risk_score,
        fa.reason,
        fa.status AS alert_status,
        t.status AS transaction_status,
        fa.created_at AS alert_created_at,
        fa.reviewed_at AS alert_reviewed_at
    FROM fraud_alerts fa
    JOIN transactions t ON fa.transaction_id = t.transaction_id
    JOIN accounts a ON fa.account_id = a.account_id
    JOIN customers c ON a.customer_id = c.customer_id
    JOIN accounts ra ON t.receiver_account_id = ra.account_id
    JOIN customers rc ON ra.customer_id = rc.customer_id;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS View_Fraud_Alerts CASCADE;")
    op.execute("DROP VIEW IF EXISTS View_Transaction_Summary CASCADE;")
    op.execute("DROP VIEW IF EXISTS View_Account_Summary CASCADE;")
    op.execute("DROP VIEW IF EXISTS View_Loan_Eligibility CASCADE;")

    op.execute("DROP TRIGGER IF EXISTS trg_enforce_ledger_immutability ON ledger_entries;")
    op.execute("DROP FUNCTION IF EXISTS fn_enforce_ledger_immutability();")
    op.execute("DROP TRIGGER IF EXISTS trg_detect_large_transfer ON transactions;")
    op.execute("DROP FUNCTION IF EXISTS fn_detect_large_transfer();")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_overdraft ON accounts;")
    op.execute("DROP FUNCTION IF EXISTS fn_prevent_overdraft();")

    op.execute("DROP TABLE IF EXISTS audit_outbox CASCADE;")
    op.execute("DROP TABLE IF EXISTS fraud_alerts CASCADE;")
    op.execute("DROP TABLE IF EXISTS loans CASCADE;")
    op.execute("DROP TABLE IF EXISTS ledger_entries CASCADE;")
    op.execute("DROP TABLE IF EXISTS transactions CASCADE;")
    op.execute("DROP TABLE IF EXISTS accounts CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")


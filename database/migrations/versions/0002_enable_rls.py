"""Enable Row Level Security (RLS) on all financial, customer, and audit tables

Revision ID: 0002_enable_rls
Revises: 0001_initial_schema
Create Date: 2026-11-04 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_enable_rls'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable RLS and FORCE on all tables
    tables = [
        'customers', 'users', 'accounts', 'transactions',
        'ledger_entries', 'loans', 'fraud_alerts', 'audit_outbox'
    ]
    for tbl in tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")

    # 2. Accounts Policy: Customers access own accounts; Admins access all
    op.execute("""
    DROP POLICY IF EXISTS p_accounts_isolation ON accounts;
    CREATE POLICY p_accounts_isolation ON accounts
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 3. Transactions Policy: Sender or receiver matches current customer
    op.execute("""
    DROP POLICY IF EXISTS p_transactions_isolation ON transactions;
    CREATE POLICY p_transactions_isolation ON transactions
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR sender_account_id IN (
            SELECT account_id FROM accounts 
            WHERE customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        )
        OR receiver_account_id IN (
            SELECT account_id FROM accounts 
            WHERE customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        )
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 4. Loans Policy: Customers access own loans; Admins access all
    op.execute("""
    DROP POLICY IF EXISTS p_loans_isolation ON loans;
    CREATE POLICY p_loans_isolation ON loans
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 5. Ledger Entries Policy
    op.execute("""
    DROP POLICY IF EXISTS p_ledger_isolation ON ledger_entries;
    CREATE POLICY p_ledger_isolation ON ledger_entries
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR account_id IN (
            SELECT account_id FROM accounts 
            WHERE customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        )
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 6. Fraud Alerts Policy
    op.execute("""
    DROP POLICY IF EXISTS p_fraud_alerts_isolation ON fraud_alerts;
    CREATE POLICY p_fraud_alerts_isolation ON fraud_alerts
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR account_id IN (
            SELECT account_id FROM accounts 
            WHERE customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        )
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 7. Customers Policy
    op.execute("""
    DROP POLICY IF EXISTS p_customers_isolation ON customers;
    CREATE POLICY p_customers_isolation ON customers
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 8. Users Policy
    op.execute("""
    DROP POLICY IF EXISTS p_users_isolation ON users;
    CREATE POLICY p_users_isolation ON users
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 9. Audit Outbox Policy
    op.execute("""
    DROP POLICY IF EXISTS p_audit_outbox_isolation ON audit_outbox;
    CREATE POLICY p_audit_outbox_isolation ON audit_outbox
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR current_setting('app.current_user_role', true) = 'SYSTEM'
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)


def downgrade() -> None:
    tables = [
        'audit_outbox', 'users', 'customers', 'fraud_alerts',
        'ledger_entries', 'loans', 'transactions', 'accounts'
    ]
    for tbl in tables:
        op.execute(f"DROP POLICY IF EXISTS p_{tbl}_isolation ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

"""Enable Row Level Security (RLS) on financial and account tables

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
    # 1. Enable RLS on core tables with FORCE to ensure table owner is also subjected to policies
    op.execute("ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE accounts FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE transactions FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ledger_entries ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ledger_entries FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE loans ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE loans FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE fraud_alerts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE fraud_alerts FORCE ROW LEVEL SECURITY;")

    # 2. Accounts Policy: Customers access own accounts; Admins access all
    op.execute("""
    DROP POLICY IF EXISTS p_accounts_isolation ON accounts;
    CREATE POLICY p_accounts_isolation ON accounts
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'ADMIN'
        OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)

    # 3. Transactions Policy: Sender or receiver customer matches current customer
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
        OR current_setting('app.current_customer_id', true) IS NULL
        OR current_setting('app.current_customer_id', true) = ''
    );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS p_loans_isolation ON loans;")
    op.execute("DROP POLICY IF EXISTS p_transactions_isolation ON transactions;")
    op.execute("DROP POLICY IF EXISTS p_accounts_isolation ON accounts;")

    op.execute("ALTER TABLE fraud_alerts DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE loans DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ledger_entries DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE accounts DISABLE ROW LEVEL SECURITY;")

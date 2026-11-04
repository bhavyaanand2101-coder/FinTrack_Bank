-- ============================================================================
-- FinTrack – Smart Digital Banking & Loan Management System
-- Database Initialization Script (PostgreSQL 14+)
-- File: database/init_db.sql
-- ============================================================================

-- Clean up existing views and tables (Order matters due to Foreign Keys)
DROP VIEW IF EXISTS View_Fraud_Alerts CASCADE;
DROP VIEW IF EXISTS View_Transaction_Summary CASCADE;
DROP VIEW IF EXISTS View_Account_Summary CASCADE;
DROP VIEW IF EXISTS View_Loan_Eligibility CASCADE;

DROP TABLE IF EXISTS audit_outbox CASCADE;
DROP TABLE IF EXISTS fraud_alerts CASCADE;
DROP TABLE IF EXISTS loans CASCADE;
DROP TABLE IF EXISTS ledger_entries CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. CUSTOMERS TABLE
-- ============================================================================
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. USERS TABLE (Authentication & Role-Based Access)
-- ============================================================================
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE SET NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'CUSTOMER' CHECK (role IN ('CUSTOMER', 'ADMIN')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. ACCOUNTS TABLE
-- ============================================================================
CREATE TABLE accounts (
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

-- ============================================================================
-- 4. TRANSACTIONS TABLE
-- ============================================================================
CREATE TABLE transactions (
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

-- ============================================================================
-- 5. LEDGER ENTRIES TABLE (Double-Entry Bookkeeping)
-- ============================================================================
CREATE TABLE ledger_entries (
    entry_id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES transactions(transaction_id) ON DELETE RESTRICT,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    entry_type VARCHAR(10) NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
    amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_ledger_amount CHECK (amount > 0.00)
);

-- ============================================================================
-- 6. LOANS TABLE
-- ============================================================================
CREATE TABLE loans (
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

-- ============================================================================
-- 7. FRAUD ALERTS TABLE
-- ============================================================================
CREATE TABLE fraud_alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    risk_score NUMERIC(10, 4) NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'APPROVED', 'REJECTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ
);

-- ============================================================================
-- 8. AUDIT OUTBOX TABLE (Transactional Outbox Pattern for MongoDB Sync)
-- ============================================================================
CREATE TABLE audit_outbox (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'DELIVERED', 'FAILED')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    last_error TEXT
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ============================================================================
CREATE INDEX idx_accounts_customer_id ON accounts(customer_id);
CREATE INDEX idx_transactions_sender ON transactions(sender_account_id);
CREATE INDEX idx_transactions_receiver ON transactions(receiver_account_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date DESC);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_ledger_account_created ON ledger_entries(account_id, created_at DESC);
CREATE INDEX idx_ledger_transaction ON ledger_entries(transaction_id);
CREATE INDEX idx_loans_customer_id ON loans(customer_id);
CREATE INDEX idx_loans_status ON loans(status);
CREATE INDEX idx_fraud_alerts_status ON fraud_alerts(status);
CREATE INDEX idx_audit_outbox_pending ON audit_outbox(status, created_at) WHERE status IN ('PENDING', 'PROCESSING');

-- Composite indexes for dashboard queries
CREATE INDEX idx_trans_sender_date ON transactions(sender_account_id, transaction_date DESC);
CREATE INDEX idx_trans_receiver_date ON transactions(receiver_account_id, transaction_date DESC);

-- ============================================================================
-- DATABASE TRIGGERS
-- ============================================================================

-- Trigger 1: Prevent Overdrafts & Maintain Updated Timestamp
CREATE OR REPLACE FUNCTION fn_prevent_overdraft()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.balance < 0.00 THEN
        RAISE EXCEPTION 'Negative balance violation: account % has insufficient funds (requested: %)',
            NEW.account_id, NEW.balance;
    END IF;
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_overdraft
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION fn_prevent_overdraft();


-- Trigger 2: Large Transfer Detection (Mandatory Flagging at Database Level)
CREATE OR REPLACE FUNCTION fn_detect_large_transfer()
RETURNS TRIGGER AS $$
BEGIN
    -- Flag transfer if >= 10,000 INR and currently requested as PENDING or SUCCESS
    IF NEW.amount >= 10000.00 AND NEW.status IN ('PENDING', 'SUCCESS') THEN
        NEW.status := 'FLAGGED';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_detect_large_transfer
BEFORE INSERT ON transactions
FOR EACH ROW
EXECUTE FUNCTION fn_detect_large_transfer();


-- Trigger 3: Ledger Immutability (Prevent committed entries from being altered or dropped)
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

CREATE TRIGGER trg_enforce_ledger_immutability
BEFORE UPDATE OR DELETE ON ledger_entries
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_ledger_immutability();


-- ============================================================================
-- DATABASE VIEWS
-- ============================================================================

-- View 1: View_Loan_Eligibility
-- Evaluates customer loan eligibility using credit score and debt-to-income ratio.
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


-- View 2: View_Account_Summary
-- Aggregates customer account balance and total debits/credits.
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


-- View 3: View_Transaction_Summary
-- Detailed overview of transactions with sender and receiver identity.
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


-- View 4: View_Fraud_Alerts
-- Administrative fraud alert console view.
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

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions FORCE ROW LEVEL SECURITY;
ALTER TABLE ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE loans FORCE ROW LEVEL SECURITY;
ALTER TABLE fraud_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_alerts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_accounts_isolation ON accounts;
CREATE POLICY p_accounts_isolation ON accounts
FOR ALL
USING (
    current_setting('app.current_user_role', true) = 'ADMIN'
    OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
    OR current_setting('app.current_customer_id', true) IS NULL
    OR current_setting('app.current_customer_id', true) = ''
);

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

DROP POLICY IF EXISTS p_loans_isolation ON loans;
CREATE POLICY p_loans_isolation ON loans
FOR ALL
USING (
    current_setting('app.current_user_role', true) = 'ADMIN'
    OR customer_id = NULLIF(current_setting('app.current_customer_id', true), '')::integer
    OR current_setting('app.current_customer_id', true) IS NULL
    OR current_setting('app.current_customer_id', true) = ''
);


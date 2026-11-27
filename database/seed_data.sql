-- ============================================================================
-- FinTrack – Smart Digital Banking & Loan Management System
-- Synthetic Seed Data Script
-- File: database/seed_data.sql
-- ============================================================================

-- 1. Insert Administrator (Password: Admin123!)
INSERT INTO users (customer_id, username, password_hash, role, is_active)
VALUES 
(NULL, 'admin', '$argon2id$v=19$m=65536,t=3,p=4$ZYvMgM4rbggunrBRzwToyA$mxMlBusR9sstHskjsf16od+xePimoKSCTw/2/6W5xqE', 'ADMIN', TRUE);

-- 2. Insert 10 Synthetic Customers
INSERT INTO customers (customer_id, full_name, email, phone) VALUES
(1, 'Arun Kumar', 'arun.kumar@example.com', '+919876543210'),
(2, 'Priya Sharma', 'priya.sharma@example.com', '+919876543211'),
(3, 'Rohit Verma', 'rohit.verma@example.com', '+919876543212'),
(4, 'Ananya Singh', 'ananya.singh@example.com', '+919876543213'),
(5, 'Vikram Patel', 'vikram.patel@example.com', '+919876543214'),
(6, 'Sneha Reddy', 'sneha.reddy@example.com', '+919876543215'),
(7, 'Rahul Mehta', 'rahul.mehta@example.com', '+919876543216'),
(8, 'Pooja Nair', 'pooja.nair@example.com', '+919876543217'),
(9, 'Kavita Joshi', 'kavita.joshi@example.com', '+919876543218'),
(10, 'Amit Gupta', 'amit.gupta@example.com', '+919876543219');

ALTER SEQUENCE customers_customer_id_seq RESTART WITH 11;

-- 3. Insert User Accounts for Customers (Password for all demo customers: Customer123!)
INSERT INTO users (customer_id, username, password_hash, role, is_active) VALUES
(1, 'arun_kumar', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(2, 'priya_sharma', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(3, 'rohit_verma', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(4, 'ananya_singh', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(5, 'vikram_patel', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(6, 'sneha_reddy', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(7, 'rahul_mehta', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(8, 'pooja_nair', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(9, 'kavita_joshi', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE),
(10, 'amit_gupta', '$argon2id$v=19$m=65536,t=3,p=4$3GzBGfSZl/mTH4zVItnHaQ$DQLmGZWLW34yhA50K05AAjovLBPB88EVugkZZcVKybY', 'CUSTOMER', TRUE);

-- 4. Insert 16 Bank Accounts (Customer 1-10)
INSERT INTO accounts (account_id, customer_id, account_type, balance, currency, is_frozen) VALUES
(1001, 1, 'SAVINGS',  74500.00, 'INR', FALSE),
(1002, 1, 'CHECKING', 25000.00, 'INR', FALSE),
(1003, 2, 'SAVINGS', 112000.00, 'INR', FALSE),
(1004, 2, 'CHECKING', 45000.00, 'INR', FALSE),
(1005, 3, 'SAVINGS',  18500.00, 'INR', FALSE),
(1006, 4, 'SAVINGS',  52000.00, 'INR', FALSE),
(1007, 4, 'CHECKING', 15000.00, 'INR', FALSE),
(1008, 5, 'SAVINGS',  88000.00, 'INR', FALSE),
(1009, 6, 'SAVINGS',  43200.00, 'INR', FALSE),
(1010, 6, 'CHECKING', 12000.00, 'INR', FALSE),
(1011, 7, 'SAVINGS',  67000.00, 'INR', FALSE),
(1012, 8, 'SAVINGS',  94000.00, 'INR', FALSE),
(1013, 8, 'CHECKING', 31000.00, 'INR', FALSE),
(1014, 9, 'SAVINGS',  50000.00, 'INR', FALSE),
(1015, 10, 'SAVINGS', 38000.00, 'INR', FALSE),
(1016, 10, 'CHECKING', 5000.00, 'INR', FALSE); -- Account 1016 will have NO transactions for Query 5 demonstration

ALTER SEQUENCE accounts_account_id_seq RESTART WITH 1017;

-- 5. Insert 50+ Historical Transactions and Balanced Ledger Entries
-- Note: Trigger 2 flags any transaction with amount >= 10000. We will set amounts accordingly.

DO $$
DECLARE
    v_tx_id BIGINT;
    v_date TIMESTAMPTZ;
BEGIN
    -- Batch 1: Routine transfers between Arun, Priya, Rohit, Ananya (Tx 1-20)
    FOR i IN 1..20 LOOP
        v_date := CURRENT_TIMESTAMP - (INTERVAL '60 days') + (i * INTERVAL '2 days');
        
        INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description, transaction_date)
        VALUES (
            1001, 1003, 
            (500.00 + (i * 75.00)), 
            'SUCCESS', 
            uuid_generate_v4(), 
            'Utility reimbursement transfer #' || i, 
            v_date
        ) RETURNING transaction_id INTO v_tx_id;

        INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount, created_at)
        VALUES 
        (v_tx_id, 1001, 'DEBIT', (500.00 + (i * 75.00)), v_date),
        (v_tx_id, 1003, 'CREDIT', (500.00 + (i * 75.00)), v_date);
    END LOOP;

    -- Batch 2: Transfers between Vikram, Sneha, Rahul, Pooja (Tx 21-40)
    FOR i IN 1..20 LOOP
        v_date := CURRENT_TIMESTAMP - (INTERVAL '45 days') + (i * INTERVAL '1.5 days');
        
        INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description, transaction_date)
        VALUES (
            1008, 1009, 
            (800.00 + (i * 120.00)), 
            'SUCCESS', 
            uuid_generate_v4(), 
            'Project consultation fee #' || i, 
            v_date
        ) RETURNING transaction_id INTO v_tx_id;

        INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount, created_at)
        VALUES 
        (v_tx_id, 1008, 'DEBIT', (800.00 + (i * 120.00)), v_date),
        (v_tx_id, 1009, 'CREDIT', (800.00 + (i * 120.00)), v_date);
    END LOOP;

    -- Batch 3: Varied transfers across multiple accounts (Tx 41-52)
    FOR i IN 1..12 LOOP
        v_date := CURRENT_TIMESTAMP - (INTERVAL '15 days') + (i * INTERVAL '1 day');
        
        INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description, transaction_date)
        VALUES (
            1011, 1012, 
            (1200.00 + (i * 250.00)), 
            'SUCCESS', 
            uuid_generate_v4(), 
            'Monthly service settlement #' || i, 
            v_date
        ) RETURNING transaction_id INTO v_tx_id;

        INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount, created_at)
        VALUES 
        (v_tx_id, 1011, 'DEBIT', (1200.00 + (i * 250.00)), v_date),
        (v_tx_id, 1012, 'CREDIT', (1200.00 + (i * 250.00)), v_date);
    END LOOP;

    -- Batch 4: Flagged / Suspicious Transfers (Amount >= 10,000 INR)
    -- Suspicious Transfer 1
    INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description, transaction_date)
    VALUES (
        1001, 1005, 18500.00, 'FLAGGED', uuid_generate_v4(), 
        'Urgent high-value emergency wire', CURRENT_TIMESTAMP - INTERVAL '3 days'
    ) RETURNING transaction_id INTO v_tx_id;

    INSERT INTO fraud_alerts (transaction_id, account_id, risk_score, reason, status, created_at)
    VALUES (v_tx_id, 1001, 3.8500, 'High value transfer (INR 18,500.00) exceeds mandatory limit and deviates from 60-day baseline (Z-score +3.85).', 'OPEN', CURRENT_TIMESTAMP - INTERVAL '3 days');

    -- Suspicious Transfer 2
    INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description, transaction_date)
    VALUES (
        1008, 1002, 25000.00, 'FLAGGED', uuid_generate_v4(), 
        'Bulk asset purchase deposit', CURRENT_TIMESTAMP - INTERVAL '1 day'
    ) RETURNING transaction_id INTO v_tx_id;

    INSERT INTO fraud_alerts (transaction_id, account_id, risk_score, reason, status, created_at)
    VALUES (v_tx_id, 1008, 4.2100, 'Transfer amount (INR 25,000.00) exceeds fraud threshold (INR 10,000.00). Flagged for compliance review.', 'OPEN', CURRENT_TIMESTAMP - INTERVAL '1 day');

    -- Suspicious Transfer 3 (Reviewed & Rejected)
    INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description, transaction_date)
    VALUES (
        1005, 1014, 50000.00, 'FAILED', uuid_generate_v4(), 
        'Overseas crypto wallet top-up', CURRENT_TIMESTAMP - INTERVAL '5 days'
    ) RETURNING transaction_id INTO v_tx_id;

    INSERT INTO fraud_alerts (transaction_id, account_id, risk_score, reason, status, created_at, reviewed_at)
    VALUES (v_tx_id, 1005, 7.8000, 'Extreme outlier transfer: insufficient balance and suspicious destination pattern.', 'REJECTED', CURRENT_TIMESTAMP - INTERVAL '5 days', CURRENT_TIMESTAMP - INTERVAL '4 days');

END $$;

-- 6. Insert 5 Loan Applications
INSERT INTO loans (loan_id, customer_id, requested_amount, annual_income, credit_score, interest_rate, status, applied_at, reviewed_at, reviewed_by) VALUES
(1, 1, 50000.00,  600000.00, 780, 8.50,  'APPROVED', CURRENT_TIMESTAMP - INTERVAL '15 days', CURRENT_TIMESTAMP - INTERVAL '14 days', 1),
(2, 2, 150000.00, 850000.00, 810, 7.50,  'APPROVED', CURRENT_TIMESTAMP - INTERVAL '10 days', CURRENT_TIMESTAMP - INTERVAL '9 days',  1),
(3, 3, 500000.00, 350000.00, 580, 15.00, 'REJECTED', CURRENT_TIMESTAMP - INTERVAL '8 days',  CURRENT_TIMESTAMP - INTERVAL '7 days',  1),
(4, 4, 100000.00, 550000.00, 720, 10.00, 'PENDING',  CURRENT_TIMESTAMP - INTERVAL '2 days',  NULL, NULL),
(5, 5, 200000.00, 700000.00, 690, 11.50, 'PENDING',  CURRENT_TIMESTAMP - INTERVAL '1 day',   NULL, NULL);

ALTER SEQUENCE loans_loan_id_seq RESTART WITH 6;


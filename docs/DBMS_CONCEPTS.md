# FinTrack — Advanced Database Management System (DBMS) Concepts

This document provides academic and professional documentation of the database engineering concepts implemented within FinTrack.

---

## 1. Relational Database Normalization (3NF)

The FinTrack relational schema satisfies **First (1NF)**, **Second (2NF)**, and **Third Normal Form (3NF)**:

### 1.1 First Normal Form (1NF)
- All attributes contain only atomic, scalar values (no repeating groups, multi-valued attributes, or nested arrays).
- Every table has a well-defined primary key (`customer_id`, `account_id`, `transaction_id`, etc.).

### 1.2 Second Normal Form (2NF)
- The schema is in 1NF.
- All non-key attributes are fully functionally dependent on the entire primary key (no partial dependencies on composite keys). Tables such as `ledger_entries` isolate individual movements under a single surrogate primary key `entry_id`.

### 1.3 Third Normal Form (3NF)
- The schema is in 2NF.
- No transitive dependencies exist (non-prime attributes do not depend on other non-prime attributes).
  - For example, customer address, name, and phone reside solely in `customers`. The `accounts` table references `customer_id` as a foreign key and does NOT duplicate customer name or email.
  - The `transactions` table references `sender_account_id` and `receiver_account_id` without duplicating customer KYC data.

---

## 2. ACID Transaction Properties

Every financial fund transfer strictly guarantees ACID properties:

1. **Atomicity**: The deduction of funds from the sender, the addition of funds to the receiver, the creation of balanced ledger entries, and the generation of the outbox audit record occur within a single PostgreSQL transaction block. If any step fails (e.g., overdraft violation), the entire transaction rolls back cleanly.
2. **Consistency**: The database invariants are enforced by triggers (`trg_prevent_overdraft`) and check constraints (`balance >= 0.00`). No balance can become negative. The double-entry invariant (Total Debits == Total Credits) is strictly maintained.
3. **Isolation**: FinTrack uses `SELECT ... FOR UPDATE` row-level locks to prevent dirty reads, non-repeatable reads, and phantom writes.
4. **Durability**: Once a transaction commits, its changes are written to the Write-Ahead Log (WAL) on disk, surviving power loss or application restarts.

---

## 3. Concurrency Control & Deadlock Prevention

### Problem: The Cross-Transfer Deadlock
If Customer A transfers money to Customer B while Customer B simultaneously transfers money to Customer A:
- Thread 1 locks Account A and waits for Account B.
- Thread 2 locks Account B and waits for Account A.
- Result: **Database Deadlock (PostgreSQL Error 40P01)**.

### Solution: Deterministic Ascending Account Locking
FinTrack eliminates deadlocks by sorting the account IDs in deterministic ascending order before acquiring `FOR UPDATE` locks:

```python
# Deterministic lock ordering in transfer_service.py:
first_acc_id = min(sender_account_id, receiver_account_id)
second_acc_id = max(sender_account_id, receiver_account_id)

cur.execute("SELECT account_id, balance, is_frozen FROM accounts WHERE account_id = %s FOR UPDATE;", (first_acc_id,))
cur.execute("SELECT account_id, balance, is_frozen FROM accounts WHERE account_id = %s FOR UPDATE;", (second_acc_id,))
```

Regardless of transfer direction ($A \to B$ or $B \to A$), both concurrent threads request lock $A$ first, then lock $B$. The second thread cleanly waits for the first thread to complete, completely preventing deadlocks.

---

## 4. Double-Entry Bookkeeping Ledger

In compliance with standard accounting practices, money is never created or destroyed arbitrarily. Every transfer is represented by balanced ledger entries in `ledger_entries`:
- **Debit Entry**: Debits the sender's account.
- **Credit Entry**: Credits the receiver's account.

$$\sum \text{Debits} = \sum \text{Credits}$$

Historical ledger entries are protected by `trg_enforce_ledger_immutability`, preventing retroactive updates or deletions.

---

## 5. The Five Advanced SQL Queries

### Query 1: Window Functions (Running Balance Statement)
Calculates running balances dynamically across historical transactions without requiring table updates:
```sql
SELECT 
    le.entry_id,
    le.transaction_id,
    t.transaction_date,
    le.entry_type,
    le.amount,
    CASE 
        WHEN le.entry_type = 'CREDIT' THEN le.amount
        ELSE -le.amount 
    END AS net_amount,
    SUM(CASE 
        WHEN le.entry_type = 'CREDIT' THEN le.amount 
        ELSE -le.amount 
    END) OVER (
        PARTITION BY le.account_id 
        ORDER BY t.transaction_date ASC, le.entry_id ASC
    ) AS running_balance,
    t.description
FROM ledger_entries le
JOIN transactions t ON le.transaction_id = t.transaction_id
WHERE le.account_id = %s AND t.status = 'SUCCESS'
ORDER BY t.transaction_date DESC, le.entry_id DESC
LIMIT %s;
```

### Query 2: Common Table Expressions (CTE for Monthly Volume)
Aggregates monthly transfer trends using a CTE:
```sql
WITH monthly_metrics AS (
    SELECT 
        DATE_TRUNC('month', transaction_date) AS month_start,
        COUNT(transaction_id) AS transfer_count,
        COALESCE(SUM(amount), 0.00) AS total_volume
    FROM transactions
    WHERE status = 'SUCCESS'
    GROUP BY DATE_TRUNC('month', transaction_date)
)
SELECT 
    TO_CHAR(month_start, 'YYYY-MM') AS month_label,
    transfer_count,
    total_volume
FROM monthly_metrics
ORDER BY month_label ASC;
```

### Query 3: Database Views (Encapsulation)
Aggregates customer summaries dynamically without redundant tables:
```sql
CREATE OR REPLACE VIEW View_Account_Summary AS
SELECT 
    a.account_id,
    a.customer_id,
    c.full_name AS customer_name,
    a.account_type,
    a.balance,
    a.is_frozen,
    COALESCE(SUM(CASE WHEN le.entry_type = 'CREDIT' THEN le.amount ELSE 0.00 END), 0.00) AS total_incoming_amount,
    COALESCE(SUM(CASE WHEN le.entry_type = 'DEBIT' THEN le.amount ELSE 0.00 END), 0.00) AS total_outgoing_amount,
    COUNT(DISTINCT le.transaction_id) AS total_transactions_count
FROM accounts a
JOIN customers c ON a.customer_id = c.customer_id
LEFT JOIN ledger_entries le ON a.account_id = le.account_id
GROUP BY a.account_id, a.customer_id, c.full_name, a.account_type, a.balance, a.is_frozen;
```

### Query 4: Subqueries & GROUP BY (Top 5 Customers)
Ranks high-volume customers by outbound transaction activity:
```sql
SELECT 
    c.customer_id,
    c.full_name,
    c.email,
    COUNT(t.transaction_id) AS total_transfers_sent,
    COALESCE(SUM(t.amount), 0.00) AS total_amount_transferred
FROM customers c
JOIN accounts a ON c.customer_id = a.customer_id
JOIN transactions t ON a.account_id = t.sender_account_id
WHERE t.status = 'SUCCESS'
GROUP BY c.customer_id, c.full_name, c.email
ORDER BY total_amount_transferred DESC
LIMIT 5;
```

### Query 5: Outer Joins (Dormant Accounts Detection)
Identifies inactive accounts that have never sent or received a transfer using `LEFT JOIN ... WHERE transaction_id IS NULL`:
```sql
SELECT 
    a.account_id,
    c.full_name AS customer_name,
    c.email AS customer_email,
    a.account_type,
    a.balance,
    a.created_at
FROM accounts a
JOIN customers c ON a.customer_id = c.customer_id
LEFT JOIN transactions t 
    ON (a.account_id = t.sender_account_id OR a.account_id = t.receiver_account_id)
WHERE t.transaction_id IS NULL
ORDER BY a.created_at ASC;
```

---

## 6. The Transactional Outbox Pattern

The Transactional Outbox pattern guarantees **at-least-once delivery** of audit logs across two heterogeneous storage systems (PostgreSQL and MongoDB) without requiring heavy two-phase commit (2PC) protocols:

1. **Local Transaction**: The business mutation (transfer, loan decision, user login) and the outbox event record are committed together in PostgreSQL.
2. **Asynchronous Polling**: The `audit_worker.py` daemon claims batches using `FOR UPDATE SKIP LOCKED`.
3. **Idempotent Delivery**: MongoDB enforces uniqueness on `event_id`, ensuring network retries cannot produce duplicate audit documents.
4. **Fault Tolerance**: If MongoDB is unreachable, PostgreSQL continues processing financial transfers uninterrupted. The outbox buffers events until MongoDB recovers.


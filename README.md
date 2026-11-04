# FinTrack – Smart Digital Banking & Loan Management System

FinTrack is an academic banking simulator and loan management system built with **Python**, **Streamlit**, **PostgreSQL**, and **MongoDB Atlas / Local NoSQL**.

The system demonstrates relational database engineering, financial ACID transactions, double-entry bookkeeping, deadlock prevention via deterministic lock ordering, statistical AI/ML anomaly detection, and the **Transactional Outbox Pattern** for asynchronous NoSQL security audit log delivery.

---

## 1. Project Introduction & Objectives

FinTrack simulates modern retail banking workflows:
- **Customer Portal**: Registration, secure authentication, account balance and running ledger tracking, immediate fund transfers, loan applications, and monthly spending analysis.
- **Administrator Console**: System metrics, loan approvals/rejections, fraud & compliance reviews for flagged transfers, and inspection of MongoDB security logs.
- **Enterprise-Grade Constraints**: Zero floating-point math (Python `Decimal` and PostgreSQL `NUMERIC(15,2)`), idempotency deduplication keys, and ledger immutability triggers.

---

## 2. Technology Stack

| Layer | Component | Description |
| :--- | :--- | :--- |
| **Frontend UI** | Streamlit | Responsive multipage dashboard with modern fintech styling |
| **Backend Runtime** | Python 3.14 / 3.13 | High-performance Python backend services |
| **Primary Database** | PostgreSQL 16 | Relational core for customer, account, transaction & ledger data |
| **NoSQL Database** | MongoDB Atlas / Local | Immutable append-only audit & security event logs |
| **Database Driver** | `psycopg2-binary` | Thread-safe connection pooling with context managers |
| **NoSQL Driver** | `pymongo` | Connection pooling and idempotent document ingestion |
| **AI / ML Engine** | Scikit-Learn & NumPy | Statistical Z-score anomaly detection with rule fallbacks |
| **Security & Auth** | `argon2-cffi` | Argon2id memory-hard password hashing |
| **Database Migrations**| Alembic & SQLAlchemy | Versioned database schema migrations |
| **Automated Testing** | Pytest & Pytest-Cov | Comprehensive test suite covering concurrency, fraud & ACID |

---

## 3. System Architecture

```mermaid
flowchart TD
    Client["Streamlit Multipage Web App"]
    AuthSvc["Auth Service (Argon2id)"]
    TxSvc["Transfer Service (ACID + Locks)"]
    ML["ML Engine (Z-Score & Rules)"]
    LoanSvc["Loan Service (Credit Model)"]
    
    subgraph PostgreSQL ["PostgreSQL Relational DB"]
        Acc["accounts (SELECT FOR UPDATE)"]
        Tx["transactions"]
        Ledger["ledger_entries (Double-Entry)"]
        Outbox["audit_outbox (Transactional Outbox)"]
        Triggers["Database Triggers & Views"]
    end
    
    subgraph AsyncWorker ["Background Outbox Worker"]
        Relay["workers/audit_worker.py (SKIP LOCKED)"]
    end
    
    subgraph NoSQL ["MongoDB Atlas / Community"]
        SecurityLogs["security_logs collection (Unique event_id)"]
    end

    Client --> AuthSvc
    Client --> TxSvc
    Client --> LoanSvc
    TxSvc --> ML
    TxSvc --> Acc
    TxSvc --> Tx
    TxSvc --> Ledger
    TxSvc --> Outbox
    Outbox -.->|Async Polling| Relay
    Relay -->|Idempotent Delivery| SecurityLogs
```

---

## 4. Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    customers ||--o{ users : "authenticates as"
    customers ||--|{ accounts : "owns"
    customers ||--o{ loans : "applies for"
    accounts ||--o{ transactions : "sends"
    accounts ||--o{ transactions : "receives"
    transactions ||--|{ ledger_entries : "produces exactly 2"
    accounts ||--o{ ledger_entries : "tracked in"
    transactions ||--o| fraud_alerts : "triggers"
    accounts ||--o{ fraud_alerts : "flagged on"
    users ||--o{ loans : "reviews"

    customers {
        int customer_id PK
        string full_name
        string email UK
        string phone UK
        timestamptz created_at
    }

    users {
        int user_id PK
        int customer_id FK
        string username UK
        string password_hash
        string role "CUSTOMER or ADMIN"
        boolean is_active
        timestamptz created_at
    }

    accounts {
        bigint account_id PK
        int customer_id FK
        string account_type "SAVINGS or CHECKING"
        numeric balance "CHECK (balance >= 0.00)"
        string currency "INR"
        boolean is_frozen
        timestamptz created_at
        timestamptz updated_at
    }

    transactions {
        bigint transaction_id PK
        bigint sender_account_id FK
        bigint receiver_account_id FK
        numeric amount "CHECK (amount > 0.00)"
        string status "PENDING, SUCCESS, FAILED, FLAGGED"
        uuid idempotency_key UK
        text description
        timestamptz transaction_date
    }

    ledger_entries {
        bigint entry_id PK
        bigint transaction_id FK
        bigint account_id FK
        string entry_type "DEBIT or CREDIT"
        numeric amount "CHECK (amount > 0.00)"
        timestamptz created_at
    }

    loans {
        bigint loan_id PK
        int customer_id FK
        numeric requested_amount
        numeric annual_income
        int credit_score
        numeric interest_rate
        string status "PENDING, APPROVED, REJECTED"
        timestamptz applied_at
        timestamptz reviewed_at
        int reviewed_by FK
    }

    fraud_alerts {
        bigint alert_id PK
        bigint transaction_id FK
        bigint account_id FK
        numeric risk_score
        text reason
        string status "OPEN, APPROVED, REJECTED"
        timestamptz created_at
        timestamptz reviewed_at
    }

    audit_outbox {
        uuid event_id PK
        string event_type
        jsonb payload
        string status "PENDING, PROCESSING, DELIVERED, FAILED"
        int retry_count
        timestamptz created_at
        timestamptz processed_at
        text last_error
    }
```

---

## 5. Database Normalization (Up to 3NF)

1. **First Normal Form (1NF)**:
   - All attributes contain atomic, scalar values (no multi-valued lists or nested record types).
   - Each table possesses an explicit primary key (`customer_id`, `user_id`, `account_id`, `transaction_id`, `entry_id`, `loan_id`, `alert_id`, `event_id`).
   - All columns have fixed data types.
2. **Second Normal Form (2NF)**:
   - All relations are in 1NF.
   - All non-key attributes are fully functionally dependent on the entire primary key (no partial key dependencies).
3. **Third Normal Form (3NF)**:
   - All relations are in 2NF.
   - No transitive dependencies exist. For example, customer contact information is kept strictly in `customers`, user login credentials in `users`, and financial account state in `accounts`. Transactions reference accounts by foreign key, eliminating data duplication.

---

## 6. Financial ACID Properties & Concurrency Control

- **Atomicity**: Fund transfers execute in a single Python-controlled database transaction. If any debit, credit, transaction record, ledger entry, or outbox write fails, the entire transaction is rolled back, leaving balances untouched.
- **Consistency**: Database CHECK constraints (`balance >= 0.00`, `amount > 0.00`, `sender <> receiver`) and triggers guarantee that invalid states cannot be persisted.
- **Isolation**: Row-level locking using `SELECT ... FOR UPDATE` prevents dirty reads, non-repeatable reads, and phantom reads.
- **Durability**: Committed records are persisted to disk in PostgreSQL with WAL (Write-Ahead Logging).

### Deadlock Avoidance Strategy
When accounts $A$ and $B$ transfer money to each other simultaneously, traditional locks can deadlock ($A$ locks 1 then waits for 2; $B$ locks 2 then waits for 1).
FinTrack enforces **Deterministic Ascending Lock Ordering**:
```sql
SELECT account_id, customer_id, balance, currency, is_frozen
FROM accounts
WHERE account_id IN (sender_id, receiver_id)
ORDER BY account_id ASC
FOR UPDATE;
```
Because both threads lock lower `account_id` first and higher `account_id` second, circular wait is mathematically eliminated.

---

## 7. Database Triggers & Views

### Database Triggers
1. **`trg_prevent_overdraft`**: Runs `BEFORE UPDATE` on `accounts`. Rejects any update attempting to set `balance < 0.00` and automatically refreshes `updated_at`.
2. **`trg_detect_large_transfer`**: Runs `BEFORE INSERT` on `transactions`. If `amount >= 10,000.00 INR`, intercepts the status and sets it to `FLAGGED` to prevent unauthorized money movement before review.
3. **`trg_enforce_ledger_immutability`**: Runs `BEFORE UPDATE OR DELETE` on `ledger_entries`. Throws an exception prohibiting alteration or deletion of double-entry records.

### Database Views
1. **`View_Loan_Eligibility`**: Calculates debt-to-income limits (max 50% of annual income), credit score tiers, pre-approval status, and suggested interest rates (7.50% to 15.00%).
2. **`View_Account_Summary`**: Aggregates customer account balances, incoming credit sums, outgoing debit sums, and total transaction counts.
3. **`View_Transaction_Summary`**: Joins transactions with sender and receiver identities.
4. **`View_Fraud_Alerts`**: Joins open and reviewed fraud alerts with counterparty information for administrator compliance consoles.

---

## 8. Five Advanced SQL Queries

### Query 1: Running Balance (Window Functions)
Calculates running balances over chronological ledger entries:
```sql
SELECT 
    entry_id,
    account_id,
    entry_type,
    amount,
    created_at,
    SUM(CASE WHEN entry_type = 'CREDIT' THEN amount ELSE -amount END) 
        OVER (PARTITION BY account_id ORDER BY created_at ASC, entry_id ASC) AS running_balance
FROM ledger_entries
WHERE account_id = 1001
ORDER BY created_at DESC, entry_id DESC
LIMIT 10;
```

### Query 2: Monthly Spending Analysis (Common Table Expression)
Aggregates outgoing volume grouped by calendar month using a CTE:
```sql
WITH monthly_outgoing AS (
    SELECT 
        sender_account_id AS account_id,
        DATE_TRUNC('month', transaction_date) AS month_start,
        SUM(amount) AS total_monthly_outgoing,
        COUNT(transaction_id) AS transfer_count
    FROM transactions
    WHERE sender_account_id = 1001 AND status = 'SUCCESS'
    GROUP BY sender_account_id, DATE_TRUNC('month', transaction_date)
)
SELECT 
    TO_CHAR(month_start, 'YYYY-MM') AS month_label,
    total_monthly_outgoing,
    transfer_count
FROM monthly_outgoing
ORDER BY month_label ASC;
```

### Query 3: Loan Eligibility (View Calculation)
Evaluates credit tiers and debt caps:
```sql
SELECT * FROM View_Loan_Eligibility WHERE customer_id = 1;
```

### Query 4: Top Five Customers by Outgoing Transfer Volume
Uses `GROUP BY`, `SUM`, `ORDER BY`, and `LIMIT`:
```sql
SELECT 
    c.customer_id,
    c.full_name,
    c.email,
    COUNT(t.transaction_id) AS successful_transfers_count,
    SUM(t.amount) AS total_outgoing_volume
FROM customers c
JOIN accounts a ON c.customer_id = a.customer_id
JOIN transactions t ON a.account_id = t.sender_account_id
WHERE t.status = 'SUCCESS'
GROUP BY c.customer_id, c.full_name, c.email
ORDER BY total_outgoing_volume DESC
LIMIT 5;
```

### Query 5: Dormant Accounts Without Transactions
Identifies accounts with no transfer history using `LEFT JOIN ... IS NULL`:
```sql
SELECT 
    a.account_id,
    a.account_type,
    a.balance,
    c.customer_id,
    c.full_name,
    c.email
FROM accounts a
JOIN customers c ON a.customer_id = c.customer_id
LEFT JOIN transactions t_send ON a.account_id = t_send.sender_account_id
LEFT JOIN transactions t_recv ON a.account_id = t_recv.receiver_account_id
WHERE t_send.transaction_id IS NULL AND t_recv.transaction_id IS NULL;
```

---

## 9. AI/ML Fraud Detection Engine

Located in `ml/ml_engine.py`:
- **Formula**:
  $$Z = \frac{X - \mu}{\sigma}$$
  Where $X$ is the current transfer amount, $\mu$ is the mean of past successful outgoing transfers, and $\sigma$ is the sample standard deviation.
- **Cold-Start Safeguard**: If $< 5$ historical transactions exist, uses rule-based validation (flags if $\ge \text{INR } 10,000$, clears otherwise).
- **Zero-Variance Fallback**: If $\sigma = 0$ (all past transfers identical), flags if amount $> 2\mu$ or $\ge 10,000$.
- **Hard Rule**: Mandatory threshold of INR 10,000.00 flags transactions regardless of history.
- **Zero Money Movement Guarantee**: Flagged transfers are recorded with `status='FLAGGED'`, zero ledger entries, and zero balance modification until administrative review.

---

## 10. Transactional Outbox Pattern & MongoDB Integration

```mermaid
sequenceDiagram
    participant App as Transfer Service
    participant PG as PostgreSQL (Transactional Core)
    participant Worker as Outbox Worker Daemon
    participant Mongo as MongoDB Atlas (security_logs)

    App->>PG: BEGIN TRANSACTION
    App->>PG: Deduct Sender & Credit Receiver
    App->>PG: Insert SUCCESS Transaction
    App->>PG: Insert 2 Balanced Ledger Entries
    App->>PG: INSERT INTO audit_outbox (status='PENDING')
    App->>PG: COMMIT TRANSACTION
    Note over App,PG: Financial operation complete and durable!

    loop Async Polling (Every 3s)
        Worker->>PG: SELECT ... FOR UPDATE SKIP LOCKED
        Worker->>PG: UPDATE status='PROCESSING'
        Worker->>Mongo: insert_one(doc) (Unique event_id index)
        alt Mongo Success
            Worker->>PG: UPDATE status='DELIVERED'
        else Mongo Downtime / Error
            Worker->>PG: UPDATE status='PENDING', retry_count++
        end
    end
```

---

## 11. Installation & Setup Instructions

### Prerequisites
- Python 3.12, 3.13, or 3.14
- PostgreSQL 14+ (Local, Supabase, or Neon.tech)
- MongoDB (Local or MongoDB Atlas)

### Step 1: Clone and Set Up Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```
Example `.env`:
```ini
POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/fintrack?sslmode=prefer
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=fintrack_db
DB_POOL_MIN=1
DB_POOL_MAX=10
FRAUD_THRESHOLD=10000.00
Z_SCORE_THRESHOLD=3.0
SESSION_TIMEOUT_MINUTES=30
```

### Step 3: Initialize Database Schema & Seed Data
```bash
# Initialize schema, triggers, and views
psql -d fintrack -f database/init_db.sql

# Load synthetic seed data
psql -d fintrack -f database/seed_data.sql

# Mark Alembic migration revision head
alembic stamp head
```

---

## 12. Running the Application

### Launch Streamlit Portal
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Launch Background Audit Outbox Worker (Optional / Concurrent)
```bash
# Run continuous background worker
python workers/audit_worker.py --interval 3.0

# Or run a single batch sync
python workers/audit_worker.py --once
```

---

## 13. Running the Automated Test Suite

FinTrack includes a comprehensive automated test suite with **49 tests** covering transactions, concurrency, idempotency, fraud detection, and NoSQL synchronization:

```bash
pytest tests/ --cov=services --cov=database_layer --cov=ml --cov=workers -v
```

All 49 tests run against an isolated test database (`fintrack_test`), preserving development records.

---

## 14. Documented Academic Demo Credentials

| Role | Username | Password | Default Accounts | Initial Balance | Highlights |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `AdminPassword123!` | N/A | N/A | Full Administrative, Loan Approval & Fraud Access |
| **Customer** | `arun_kumar` | `Customer123!` | `1001` (Savings)<br>`1002` (Checking) | ₹74,500.00<br>₹25,000.00 | Rich transfer history, approved loan |
| **Customer** | `priya_sharma` | `Customer123!` | `1003` (Savings)<br>`1004` (Checking) | ₹112,000.00<br>₹45,000.00 | High credit score (810), approved loan |
| **Customer** | `rohit_verma` | `Customer123!` | `1005` (Savings) | ₹18,500.00 | Rejected loan & historical rejected alert |
| **Customer** | `ananya_singh` | `Customer123!` | `1006` (Savings)<br>`1007` (Checking) | ₹52,000.00<br>₹15,000.00 | Pending loan application (₹100,000.00) |
| **Customer** | `vikram_patel` | `Customer123!` | `1008` (Savings) | ₹88,000.00 | Active outgoing transfers & open fraud alert |
| **Customer** | `amit_gupta` | `Customer123!` | `1016` (Checking) | ₹5,000.00 | Zero-transaction dormant account (Query 5) |

---

## 15. Known Academic Limitations
- **Academic Simulator**: This application is built for university DBMS and AI/ML demonstration. It is not connected to real-money payment networks (NPCI, UPI, SWIFT).
- **Single Currency**: Balances and transactions default to INR (`₹`).
- **Simulated Credit Score**: Credit scores are validated within the standard 300–900 CIBIL range via algorithmic tiers rather than an external credit bureau API.


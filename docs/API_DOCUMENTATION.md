# FinTrack — REST API Specification & Endpoint Directory

**Base URL**: `http://localhost:8000/api`  
**Authentication**: Bearer JWT Token (`Authorization: Bearer <access_token>`)  
**Data Format**: JSON (`application/json`)  
**Interactive Swagger UI**: `http://localhost:8000/docs`

---

## 1. System Health
* `GET /api/health`
  * Status: `200 OK`
  * Response: `{"status": "healthy", "databases": {"postgresql": "ONLINE", "mongodb": "ONLINE"}, "engine": "FastAPI + PostgreSQL 16 + MongoDB"}`

---

## 2. Authentication Router (`/api/auth`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/auth/register` | `POST` | Public | Register new customer, user record, and primary savings account | `201 Created` |
| `/api/auth/login` | `POST` | Public | Authenticate with username and password, return JWT token | `200 OK` |
| `/api/auth/me` | `GET` | Authenticated | Retrieve current user profile and session details | `200 OK` |
| `/api/auth/logout` | `POST` | Authenticated | Terminate session and audit logout event | `200 OK` |

### Sample Register Request (`POST /api/auth/register`)
```json
{
  "full_name": "Ramesh Chandra",
  "email": "ramesh.chandra@example.com",
  "phone": "+919876543299",
  "username": "ramesh_c",
  "password": "StrongPassword123!",
  "initial_deposit": 2500.00
}
```

---

## 3. Account Operations Router (`/api/accounts`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/accounts` | `GET` | Authenticated | List all accounts owned by current user (or all if admin) | `200 OK` |
| `/api/accounts/{account_id}` | `GET` | Authenticated | Retrieve single account details with balance | `200 OK` |
| `/api/accounts/{account_id}/balance` | `GET` | Authenticated | Real-time balance inquiry | `200 OK` |
| `/api/accounts/{account_id}/summary` | `GET` | Authenticated | Aggregate summary from `View_Account_Summary` | `200 OK` |
| `/api/accounts/{account_id}/statement` | `GET` | Authenticated | Statement with running balance (Window Function Query 1) | `200 OK` |

---

## 4. Transfers Router (`/api/transfers`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/transfers` | `POST` | Customer | Execute fund transfer or place on compliance hold ($\ge$ ₹10k) | `200 OK` |
| `/api/transfers` | `GET` | Authenticated | List transactions for current customer's accounts | `200 OK` |
| `/api/transfers/{transaction_id}` | `GET` | Authenticated | Fetch specific transaction record by ID | `200 OK` |
| `/api/transfers/recipient/{account_id}` | `GET` | Customer | Pre-validate recipient account and lookup beneficiary name | `200 OK` |

### Sample Transfer Request (`POST /api/transfers`)
```json
{
  "sender_account_id": 1001,
  "receiver_account_id": 1003,
  "amount": 1500.00,
  "description": "Invoice payment #441",
  "idempotency_key": "4f54e63c-7e61-4c6e-b31c-5541bf77bb01"
}
```

---

## 5. Loan Management Router (`/api/loans` and `/api/admin/loans`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/loans/calculate` | `POST` | Authenticated | Real-time fixed-rule eligibility calculator preview | `200 OK` |
| `/api/loans` | `POST` | Customer | Submit formal personal loan application | `201 Created` |
| `/api/loans` | `GET` | Authenticated | Fetch loan applications (customers see own; admin sees all) | `200 OK` |
| `/api/admin/loans` | `GET` | Admin | Retrieve all loan applications with status filters | `200 OK` |
| `/api/admin/loans/{loan_id}/approve` | `PATCH` | Admin | Approve pending loan application | `200 OK` |
| `/api/admin/loans/{loan_id}/reject` | `PATCH` | Admin | Reject pending loan application | `200 OK` |

---

## 6. Administration & Reporting Router (`/api/admin`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/admin/dashboard` | `GET` | Admin | Fetch system-wide counters, total volume, pending queues | `200 OK` |
| `/api/admin/customers` | `GET` | Admin | Search and inspect customer directory and accounts | `200 OK` |
| `/api/admin/accounts/{account_id}/freeze` | `PATCH` | Admin | Freeze or unfreeze a customer bank account | `200 OK` |
| `/api/admin/transactions` | `GET` | Admin | Bank-wide transaction monitor | `200 OK` |
| `/api/admin/reports` | `GET` | Admin | Execute and return all 5 Advanced DBMS SQL queries | `200 OK` |

---

## 7. Compliance & Fraud Router (`/api/admin/fraud-alerts`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/admin/fraud-alerts` | `GET` | Admin | Retrieve rule-flagged transfers from `View_Fraud_Alerts` | `200 OK` |
| `/api/admin/fraud-alerts/{alert_id}/approve` | `PATCH` | Admin | Atomically approve and execute held transfer with ledger entries | `200 OK` |
| `/api/admin/fraud-alerts/{alert_id}/reject` | `PATCH` | Admin | Reject held transfer with 0 balance movement | `200 OK` |

---

## 8. Audit Logs Router (`/api/admin/audit-logs`)

| Endpoint | Method | Role | Description | Response Code |
| :--- | :---: | :---: | :--- | :---: |
| `/api/admin/audit-logs` | `GET` | Admin | Query MongoDB security logs with action/pagination filters | `200 OK` |
| `/api/admin/audit-logs/{event_id}` | `GET` | Admin | Inspect individual MongoDB security log document | `200 OK` |
| `/api/admin/audit-logs/sync` | `POST` | Admin | Trigger immediate on-demand outbox flush to MongoDB | `200 OK` |


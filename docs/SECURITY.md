# FinTrack — Security Architecture & Hardening Guide

## 1. Threat Model & Security Posture

FinTrack operates under a strict defense-in-depth model appropriate for financial and banking applications. Security controls are enforced across the network, application code, database engine, and audit layers.

---

## 2. Authentication & Credential Storage

### 2.1 Password Hashing with Argon2id
FinTrack utilizes **Argon2id**, the winner of the Password Hashing Competition (PHC) and the state of the art in password protection:
- Algorithm: Argon2id (hybrid version resilient to both side-channel and GPU/ASIC brute-force attacks).
- Memory cost: $65,536 \text{ KiB}$ ($64 \text{ MB}$).
- Time cost: 3 iterations.
- Parallelism: 4 threads.
- Passwords are never stored in plaintext, logged, or included in responses.

### 2.2 Token-Based Session Management
- **Token Type**: JSON Web Tokens (JWT) signed with HMAC-SHA256 (`HS256`).
- **Session Expiry**: 30 minutes (`SESSION_TIMEOUT_MINUTES=30`).
- **Payload**: Minimal claims (`sub`, `username`, `role`, `customer_id`, `exp`, `iat`). Sensitive financial or password information is omitted.

### 2.3 Sliding-Window Rate Limiting
To prevent brute-force credential stuffing and password guessing:
- Tracks failed attempts per username and client IP address.
- Maximum 5 failed attempts within a 300-second (5-minute) sliding window.
- Exceeding the threshold locks the account temporarily and generates a `LOGIN_LOCKED` security outbox event.

---

## 3. Database Security & Row Level Security (RLS)

### 3.1 PostgreSQL Row Level Security (RLS)
PostgreSQL 16 Row Level Security is enabled and enforced with `FORCE ROW LEVEL SECURITY` across all sensitive tables:
- `accounts`
- `customers`
- `transactions`
- `ledger_entries`
- `loans`
- `fraud_alerts`
- `audit_outbox`

When queries execute under an authenticated session context (`app.current_user_id` and `app.current_role`):
- Customers can ONLY select rows matching their own `customer_id`.
- Administrators possess unrestricted visibility for monitoring and compliance.

### 3.2 SQL Injection Prevention
All database queries use parameterized SQL placeholders (`%s`) via `psycopg2`. No user-provided string is ever concatenated or formatted directly into SQL query text.

---

## 4. Insecure Direct Object Reference (IDOR) Prevention

Every endpoint verifying ownership of an account or transaction enforces checks before executing business operations:
1. `require_customer`: Validates that the authenticated user possesses a valid `customer_id`.
2. `AccountService.get_account_detail(account_id, customer_id)`: Enforces ownership at the query level:
   ```sql
   SELECT * FROM accounts WHERE account_id = %s AND (customer_id = %s OR %s = TRUE);
   ```
   If Customer 1 attempts to view or transfer from Account 1003 (owned by Customer 2), the request is rejected with `403 Forbidden` or `404 Not Found`.

---

## 5. Input Sanitization & XSS Prevention

[`security.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/security.py) implements a comprehensive validator:
- **`sanitize_text`**: Strips HTML tags, `<script>` injection vectors, and null bytes while enforcing length limits.
- **`validate_email`**: Enforces strict RFC-compliant email structure without regex catastrophic backtracking vulnerabilities.
- **`validate_username`**: Enforces alphanumeric structure (`^[a-zA-Z0-9_]{3,30}$`).
- **`validate_transfer_amount`**: Converts inputs to Python `Decimal`, ensuring precision $\le 2$ decimal places and strictly positive values.

---

## 6. Network & Transport Security

- **Strict CORS Policy**: Configured in FastAPI middleware to whitelist only explicit frontend origins (`http://localhost:5173`, `http://127.0.0.1:5173`).
- **Security Headers**: API responses include:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: default-src 'self'`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (in production)

---

## 7. Storage Security & File Upload Isolation

Private document storage ([`services/storage_service.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/services/storage_service.py)) verifies:
- Path traversal protection: Path normalization blocks directory escapes (`../`).
- Magic byte validation: Checks file content headers rather than trusting extensions.
- Storage directory resides outside public web roots.


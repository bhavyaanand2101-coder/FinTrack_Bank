# FinTrack — Automated Testing & Quality Assurance Suite

## 1. Testing Strategy & Test Pyramids

FinTrack employs a comprehensive multi-layered automated testing suite across the entire application stack:
1. **Database & Schema Verification**: Table existence, triggers, check constraints, foreign keys, views, Row Level Security.
2. **Unit & Service Layer Tests**: Transfer service, loan calculator, auth service, Argon2id hashing, rate limiting.
3. **Concurrency & Deadlock Prevention**: Simulates simultaneous high-concurrency cross-transfers ($A \to B$ and $B \to A$).
4. **Security & IDOR Auditing**: Direct object reference attacks, XSS sanitization, rate limiting, RLS enforcement.
5. **API Endpoint Integration**: TestClient verification of all 30 REST endpoints.
6. **Frontend Component Unit Tests**: Vitest suite verifying UI component rendering and states.

---

## 2. Test Execution Commands

### 2.1 Backend Pytest Suite
```bash
# Run all backend tests with verbose output
./.venv/bin/pytest -v

# Run with test coverage report
./.venv/bin/pytest --cov=. --cov-report=term-missing
```

### 2.2 Frontend Vitest Suite
```bash
# Navigate to frontend directory and run tests
cd frontend && npm test
```

### 2.3 Frontend Production Build Verification
```bash
cd frontend && npm run build
```

---

## 3. Test Suite Directory & Breakdown

| Test File | Tests | Focus Area | Status |
| :--- | :---: | :--- | :---: |
| [`tests/test_database.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_database.py) | 7 | Schema tables, overdraft trigger, large transfer trigger, ledger immutability trigger, views, RLS enforcement | `PASSED` |
| [`tests/test_accounts.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_accounts.py) | 8 | Customer isolation, account balance lookup, freeze detection, running balance Window query, monthly CTE query | `PASSED` |
| [`tests/test_transfers.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_transfers.py) | 10 | Successful transfer, balanced ledger, insufficient balance, frozen account, idempotency, negative amount rejection | `PASSED` |
| [`tests/test_concurrency.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_concurrency.py) | 2 | Concurrent transfers prevent double spending; simultaneous opposite-direction transfers prevent deadlocks | `PASSED` |
| [`tests/test_fraud.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_fraud.py) | 2 | Deterministic threshold ($\ge$ ₹10k), zero money movement on hold, alert creation | `PASSED` |
| [`tests/test_loans.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_loans.py) | 4 | Fixed-rule eligibility calculator, input validation, loan application workflow, rejection handling | `PASSED` |
| [`tests/test_auth.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_auth.py) | 9 | Password hash verification, customer login, admin login, invalid password, inactive user, token expiration, registration, throttling | `PASSED` |
| [`tests/test_security.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_security.py) | 10 | XSS sanitization, username validation, email validation, rate limiting, file upload magic bytes, IDOR protection, webhook signatures, command guard | `PASSED` |
| [`tests/test_audit.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_audit.py) | 5 | Outbox event creation, worker delivery to MongoDB, duplicate prevention, fault-tolerance during MongoDB outage, abandoned event recovery | `PASSED` |
| [`tests/test_api_endpoints.py`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/tests/test_api_endpoints.py) | 8 | Healthcheck, auth login, /me profile, accounts isolation, transfer execution, compliance hold, loan calculator, admin operations | `PASSED` |
| [`frontend/src/App.test.jsx`](file:///Users/bhavya/Desktop/%20/Sem_3/DBMS/Capstone/frontend/src/App.test.jsx) | 3 | StatusBadge component, MetricCard financial formatting, Alert component rendering | `PASSED` |

**Total Test Count**: 70 Automated Tests  
**Pass Rate**: **100% Passing**


# FinTrack — Deployment & Production Operations Guide

## 1. Prerequisites & System Requirements

FinTrack requires the following infrastructure:
- **Operating System**: Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9) or macOS (13+).
- **Python**: Version 3.12, 3.13, or 3.14.
- **Node.js & npm**: Node.js 18+ and npm 9+.
- **Primary Database**: PostgreSQL 16+ running locally or managed (Amazon RDS, Cloud SQL).
- **Secondary Database**: MongoDB Community 7+ or MongoDB Atlas.

---

## 2. Quick Start: Local Development Launcher

A consolidated bash launcher script is provided at the repository root:
```bash
chmod +x run.sh
./run.sh
```

### What `run.sh` Does:
1. Validates that the Python virtual environment (`.venv`) exists.
2. Traps `SIGINT` (Ctrl+C) and `SIGTERM` to cleanly terminate all background subprocesses.
3. Launches the **Audit Outbox Daemon** (`workers/audit_worker.py`).
4. Launches the **FastAPI Backend Server** on `http://localhost:8000`.
5. Launches the **Vite React Frontend Server** on `http://localhost:5173`.
6. Waits for exit signals, ensuring no orphaned processes remain.

---

## 3. Production Deployment Architecture

For production environments, the application is deployed behind an **Nginx Reverse Proxy** with SSL/TLS termination:

```
[Internet Client]
       │
       ▼ (HTTPS :443)
[Nginx Reverse Proxy]
   ├── /api/* ──► [Gunicorn / Uvicorn Workers (:8000)]
   │                     │
   │                     ├──► PostgreSQL 16 (:5432)
   │                     │
   │                     └──► [Audit Worker Daemon] ──► MongoDB (:27017)
   │
   └── /*    ──► [Static Frontend Build (/var/www/fintrack/dist)]
```

### 3.1 Building the React Frontend for Production
```bash
cd frontend
npm install
npm run build
```
The compiled, minified production assets are output to `frontend/dist/`. Serve these static files directly through Nginx for maximum performance and low memory footprint.

### 3.2 Running the Backend with Gunicorn / Uvicorn
In production, run FastAPI with multiple worker processes using Gunicorn:
```bash
./.venv/bin/gunicorn api.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/fintrack/api_access.log \
    --error-logfile /var/log/fintrack/api_error.log
```

### 3.3 Running the Background Audit Daemon with Systemd
Create `/etc/systemd/system/fintrack-audit.service`:
```ini
[Unit]
Description=FinTrack Transactional Outbox Audit Worker
After=network.target postgresql.service mongod.service

[Service]
Type=simple
User=fintrack
WorkingDirectory=/opt/fintrack
ExecStart=/opt/fintrack/.venv/bin/python workers/audit_worker.py --interval 3.0
Restart=always
RestartSec=5
EnvironmentFile=/opt/fintrack/.env

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable fintrack-audit
sudo systemctl start fintrack-audit
```

---

## 4. Environment Configuration (`.env`)

FinTrack loads configuration using `pydantic-settings`. Ensure production secrets are securely set:

| Variable | Description | Example / Production Format |
| :--- | :--- | :--- |
| `POSTGRES_URI` | PostgreSQL connection string | `postgresql://fintrack_user:StrongPassword@localhost:5432/fintrack` |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/` |
| `MONGO_DB_NAME` | MongoDB database name | `fintrack_db` |
| `SECRET_KEY` | HMAC-SHA256 signing key for JWTs | High-entropy 64-character secret string |
| `FRAUD_THRESHOLD` | Compliance hold threshold amount | `10000.00` |
| `SESSION_TIMEOUT_MINUTES` | Active session timeout | `30` |
| `DB_POOL_MIN` | Min pool connections | `2` |
| `DB_POOL_MAX` | Max pool connections | `20` |

---

## 5. Database Migrations (Alembic)

To apply schema migrations cleanly to a new database:
```bash
# Run all pending migrations up to latest revision
./.venv/bin/alembic upgrade head
```
All migrations are strictly additive and preserve existing data.


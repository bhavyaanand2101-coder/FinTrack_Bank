# FinTrack — Production Docker Deployment Guide

This guide details how to build, run, and operate the complete FinTrack full-stack banking DBMS architecture using Docker and Docker Compose.

---

## 1. Stack Architecture Overview

The containerized architecture consists of 6 coordinated services running on an isolated bridge network (`fintrack-network`):

```
                                [ Browser / Client ]
                                         │
                                         ▼ (Port 8080 : 80)
                              ┌───────────────────────┐
                              │   fintrack-frontend   │
                              │ (React 18 + Nginx 1.25)│
                              └──────────┬────────────┘
                                         │ Reverse Proxy (/api, /docs, SSE)
                                         ▼ (Port 8001 : 8000)
                              ┌───────────────────────┐
                              │   fintrack-backend    │
                              │   (Python 3.12 +      │
                              │       FastAPI)        │
                              └─────┬───────────┬─────┘
                                    │           │
           ┌────────────────────────┴─┐       ┌─┴────────────────────────┐
           ▼                          ▼       ▼                          ▼
┌───────────────────────┐ ┌──────────────────────┐ ┌────────────────────────┐ ┌────────────────────────┐
│   fintrack-postgres   │ │   fintrack-mongodb   │ │ fintrack-audit-worker  │ │ fintrack-excel-worker  │
│ (PostgreSQL 16 Alpine)│ │  (MongoDB 7.0 Alpha) │ │ (Outbox -> Mongo Daemon│ │ (Live Excel Auto-Sync) │
└───────────────────────┘ └──────────────────────┘ └────────────────────────┘ └────────────────────────┘
```

---

## 2. Quick Start: One-Command Deployment

From the project root:

```bash
docker compose up -d --build
```

### Checking Deployment Status
```bash
docker compose ps
```

All 6 containers will show state `Up` and `healthy`:
- `fintrack-postgres`: Port `5433:5432`
- `fintrack-mongodb`: Port `27018:27017`
- `fintrack-backend`: Port `8001:8000`
- `fintrack-frontend`: Port `8080:80`
- `fintrack-audit-worker`: Background worker
- `fintrack-excel-sync-worker`: Background worker

---

## 3. Accessing the Application

- **Web Dashboard**: [http://localhost:8080](http://localhost:8080)
- **Live Excel Spreadsheet View**:
  - Customer: [http://localhost:8080/live-sheet](http://localhost:8080/live-sheet)
  - Admin: [http://localhost:8080/admin/live-sheet](http://localhost:8080/admin/live-sheet)
- **Direct Backend API**: [http://localhost:8001](http://localhost:8001)
- **Swagger Interactive API Documentation**: [http://localhost:8080/docs](http://localhost:8080/docs) (or [http://localhost:8001/docs](http://localhost:8001/docs))

---

## 4. Default Credentials

| Role | Username | Password |
| :--- | :--- | :--- |
| **Administrator** | `admin` | `AdminPassword123!` |
| **Customer 1** | `arun_kumar` | `Customer123!` |
| **Customer 2** | `priya_sharma` | `Customer123!` |

---

## 5. Operations & Monitoring

### Viewing Real-Time Logs
```bash
# All services
docker compose logs -f

# Specific worker logs
docker compose logs -f audit-worker
docker compose logs -f excel-sync-worker
docker compose logs -f backend
```

### Stopping the Stack
```bash
docker compose down
```

### Stopping and Purging Volumes (Clean Reset)
```bash
docker compose down -v
```

---

## 6. Production Hardening Checklist for VPS / Cloud Hosting

1. Change `PORT_FRONTEND` to `80` (or `443` with Let's Encrypt SSL/Certbot).
2. Set a high-entropy 64-character `SECRET_KEY` in your environment.
3. Change default `POSTGRES_PASSWORD` and update `POSTGRES_URI`.
4. Ensure firewall only exposes ports 80 and 443 to the public internet; internal ports (5432, 27017, 8000) stay inside the Docker network.

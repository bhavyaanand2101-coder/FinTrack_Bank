#!/usr/bin/env bash
# ============================================================================
# FinTrack - Single Command Full-Stack Launcher
# Runs FastAPI Backend (8000), Vite React Frontend (5173), and Audit Worker
# ============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=================================================================="
echo "    🏦 FinTrack: Smart Digital Banking & Loan Management DBMS     "
echo "=================================================================="

# Check Python environment
if [ ! -f "$PROJECT_DIR/.venv/bin/python" ]; then
    echo "❌ Error: Virtual environment not found at $PROJECT_DIR/.venv"
    exit 1
fi

# Clean up child processes on exit (Ctrl+C)
trap 'echo -e "\n🛑 Shutting down FinTrack services..."; kill 0' SIGINT SIGTERM EXIT

echo "▶ 1/4 Starting Background Audit Outbox Worker..."
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/workers/audit_worker.py" --interval 3.0 &
PID_WORKER=$!

echo "▶ 2/4 Starting Live Excel Auto-Sync Worker (fintrack_live_data.xlsx)..."
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/workers/excel_sync_worker.py" --interval 2.0 &
PID_EXCEL=$!

echo "▶ 3/4 Starting FastAPI Backend Server (http://localhost:8000)..."
"$PROJECT_DIR/.venv/bin/uvicorn" api.main:app --host 0.0.0.0 --port 8000 &
PID_BACKEND=$!

echo "▶ 4/4 Starting React Vite Frontend Server (http://localhost:5173)..."
(cd "$PROJECT_DIR/frontend" && npm run dev -- --host 0.0.0.0 --port 5173) &
PID_FRONTEND=$!

echo ""
echo "=================================================================="
echo "  ✓ FinTrack Full-Stack Banking System is LIVE!"
echo "  - React Web App:     http://localhost:5173"
echo "  - FastAPI Backend:   http://localhost:8000"
echo "  - API Documentation: http://localhost:8000/docs"
echo "  - Live Excel Sheet:  $PROJECT_DIR/fintrack_live_data.xlsx"
echo ""
echo "  Demo Accounts:"
echo "  • Admin:    admin / AdminPassword123!"
echo "  • Customer: arun_kumar / Customer123!"
echo "=================================================================="
echo "Press Ctrl+C to stop all services."

wait


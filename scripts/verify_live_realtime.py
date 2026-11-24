"""
FinTrack - Real-Time SSE Live Excel & Disk Auto-Sync Verification Script
Tests the ACTUAL running FastAPI (:8000), Vite (:5173), PostgreSQL, MongoDB,
and Live Excel Auto-Sync Daemon (`fintrack_live_data.xlsx`).
"""

import json
import os
from pathlib import Path
import queue
import threading
import time
import uuid

from openpyxl import load_workbook
import requests

API_BASE = "http://127.0.0.1:8000/api"
FRONTEND_URL = "http://127.0.0.1:5173"
EXCEL_FILE = Path(__file__).resolve().parent.parent / "fintrack_live_data.xlsx"


def sse_listener(stream_url: str, event_queue: queue.Queue, stop_event: threading.Event):
    """Listen to real Server-Sent Events stream and enqueue parsed snapshot dicts."""
    with requests.get(stream_url, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        event_type = None
        for raw_line in resp.iter_lines(decode_unicode=True):
            if stop_event.is_set():
                break
            if raw_line is None:
                continue
            line = raw_line.strip()
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type == "snapshot":
                payload = json.loads(line.split(":", 1)[1].strip())
                event_queue.put(payload)
                event_type = None


def main():
    print("===================================================================")
    print("   FINTRACK REAL-TIME SSE EXCEL & ACID COMMIT LIVE VERIFICATION    ")
    print("===================================================================")

    # 1. Verify FastAPI & Vite live
    h = requests.get(f"{API_BASE}/health", timeout=5).json()
    assert h["status"] == "healthy", f"Backend not healthy: {h}"
    print(f"1. Healthcheck OK -> PG={h['databases']['postgresql']}, Mongo={h['databases']['mongodb']}")

    f_res = requests.get(FRONTEND_URL, timeout=5)
    assert f_res.status_code == 200 and '<div id="root">' in f_res.text
    print(f"2. React Frontend OK -> {FRONTEND_URL} (HTTP 200)")

    # 2. Authenticate Admin & Customer
    admin_token = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
        timeout=5,
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    cust_token = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "arun_kumar", "password": "Customer123!"},
        timeout=5,
    ).json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    print("3. Auth OK -> Admin & Customer JWTs issued")

    # 3. Open live Admin SSE stream
    ev_q: queue.Queue = queue.Queue()
    stop_ev = threading.Event()
    stream_url = f"{API_BASE}/live-sheet/stream?token={admin_token}"
    listener_thread = threading.Thread(
        target=sse_listener, args=(stream_url, ev_q, stop_ev), daemon=True
    )
    listener_thread.start()

    # Wait for initial SSE snapshot
    snap_initial = ev_q.get(timeout=5)
    assert snap_initial["scope"] == "ADMIN"
    assert snap_initial["summary"]["is_balanced"] is True
    bal_1001_start = next(
        r["balance"] for r in snap_initial["sheets"]["Accounts"]["rows"] if r["account_id"] == 1001
    )
    bal_1003_start = next(
        r["balance"] for r in snap_initial["sheets"]["Accounts"]["rows"] if r["account_id"] == 1003
    )
    print(
        f"4. Live SSE Connected -> Initial Snapshot received! "
        f"Acc #1001=INR {bal_1001_start:,.2f}, Acc #1003=INR {bal_1003_start:,.2f} | "
        f"Debits==Credits ({snap_initial['summary']['total_debits']:,.2f})"
    )

    mtime_before = EXCEL_FILE.stat().st_mtime if EXCEL_FILE.exists() else 0

    # 4. Execute real ACID transfer of INR 500.00
    t0 = time.time()
    tx_res = requests.post(
        f"{API_BASE}/transfers",
        json={
            "sender_account_id": 1001,
            "receiver_account_id": 1003,
            "amount": 500.00,
            "description": "Live Real-Time SSE Verification Transfer",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=cust_headers,
        timeout=5,
    ).json()
    assert tx_res["status"] == "SUCCESS", f"Expected SUCCESS, got {tx_res}"
    tx_id_500 = tx_res["transaction_id"]

    # Wait for SSE stream to push the real-time update automatically!
    snap_after_500 = ev_q.get(timeout=5)
    latency_ms = (time.time() - t0) * 1000
    bal_1001_after = next(
        r["balance"] for r in snap_after_500["sheets"]["Accounts"]["rows"] if r["account_id"] == 1001
    )
    bal_1003_after = next(
        r["balance"] for r in snap_after_500["sheets"]["Accounts"]["rows"] if r["account_id"] == 1003
    )
    assert round(bal_1001_start - bal_1001_after, 2) == 500.00
    assert round(bal_1003_after - bal_1003_start, 2) == 500.00
    assert snap_after_500["summary"]["is_balanced"] is True
    print(
        f"5. LIVE SSE PUSH IN {latency_ms:.0f}ms -> Tx #{tx_id_500} (INR 500.00)! "
        f"Acc #1001: {bal_1001_start:,.2f} -> {bal_1001_after:,.2f} (-500.00) | "
        f"Acc #1003: {bal_1003_start:,.2f} -> {bal_1003_after:,.2f} (+500.00) | BALANCED ✓"
    )

    # 5. Execute real compliance hold >= INR 10,000.00 (zero balance movement)
    t1 = time.time()
    hold_res = requests.post(
        f"{API_BASE}/transfers",
        json={
            "sender_account_id": 1001,
            "receiver_account_id": 1003,
            "amount": 10000.00,
            "description": "Live SSE Compliance Hold Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=cust_headers,
        timeout=5,
    ).json()
    assert hold_res["status"] == "FLAGGED"
    alert_id = hold_res["alert_id"]

    snap_after_hold = ev_q.get(timeout=5)
    hold_latency_ms = (time.time() - t1) * 1000
    bal_1001_hold = next(
        r["balance"] for r in snap_after_hold["sheets"]["Accounts"]["rows"] if r["account_id"] == 1001
    )
    assert bal_1001_hold == bal_1001_after, "Balance must NOT move on compliance hold!"
    print(
        f"6. LIVE SSE PUSH IN {hold_latency_ms:.0f}ms -> Alert #{alert_id} FLAGGED (INR 10,000.00) | "
        f"Acc #1001 UNCHANGED at {bal_1001_hold:,.2f} (0 movement) ✓"
    )

    # 6. Admin rejects the test hold so balance stays clean, verify SSE push
    t2 = time.time()
    rej_res = requests.patch(
        f"{API_BASE}/admin/fraud-alerts/{alert_id}/reject",
        json={"notes": "Automated live SSE test cleanup"},
        headers=admin_headers,
        timeout=5,
    )
    assert rej_res.status_code == 200
    snap_after_rej = ev_q.get(timeout=5)
    rej_latency_ms = (time.time() - t2) * 1000
    assert snap_after_rej["summary"]["is_balanced"] is True
    print(
        f"7. LIVE SSE PUSH IN {rej_latency_ms:.0f}ms -> Admin REJECTED Alert #{alert_id} | "
        f"Debits==Credits ({snap_after_rej['summary']['total_debits']:,.2f}) ✓"
    )

    # Stop SSE listener cleanly
    stop_ev.set()

    # 7. Verify disk Excel workbook (`fintrack_live_data.xlsx`) was AUTO-UPDATED by the background daemon!
    print("8. Waiting up to 4s for Background Excel Daemon to auto-sync fintrack_live_data.xlsx...")
    updated_on_disk = False
    for _ in range(16):
        if EXCEL_FILE.exists() and EXCEL_FILE.stat().st_mtime > mtime_before:
            updated_on_disk = True
            break
        time.sleep(0.25)

    assert updated_on_disk, "fintrack_live_data.xlsx was not automatically updated!"
    wb = load_workbook(EXCEL_FILE)
    tx_ws = wb["Transactions"]
    tx_ids_in_excel = [tx_ws.cell(row=r, column=1).value for r in range(2, min(tx_ws.max_row + 1, 30))]
    assert tx_id_500 in tx_ids_in_excel, f"Tx #{tx_id_500} not found in fintrack_live_data.xlsx!"
    print(
        f"   ✓ fintrack_live_data.xlsx AUTO-UPDATED on disk ({EXCEL_FILE.stat().st_size / 1024:.1f} KB) "
        f"and contains live Tx #{tx_id_500}!"
    )

    # 8. Verify live .xlsx download endpoints
    dl_admin = requests.get(f"{API_BASE}/admin/export-excel", headers=admin_headers, timeout=10)
    assert dl_admin.status_code == 200 and len(dl_admin.content) > 5000
    dl_cust = requests.get(f"{API_BASE}/accounts/export-excel", headers=cust_headers, timeout=10)
    assert dl_cust.status_code == 200 and len(dl_cust.content) > 3000
    print(
        f"9. Excel Download APIs OK -> Admin={len(dl_admin.content)/1024:.1f} KB, "
        f"Customer={len(dl_cust.content)/1024:.1f} KB"
    )

    print("===================================================================")
    print("   ALL 9 REAL-TIME SSE, ACID & AUTO-SYNC EXCEL CHECKS PASSED 100%! ")
    print("===================================================================")


if __name__ == "__main__":
    main()

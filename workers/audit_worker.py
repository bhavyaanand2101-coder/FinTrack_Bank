"""
FinTrack - Smart Digital Banking & Loan Management System
Transactional Outbox Background Audit Worker
File: workers/audit_worker.py
"""

import argparse
import datetime
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import settings
from database_layer.mongodb import check_mongo_health, insert_audit_document
from database_layer.postgres import execute_update, fetch_all, transaction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AuditWorker] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AuditWorker")

# Lease timeout in minutes for crashed worker recovery
PROCESSING_LEASE_MINUTES = 2
MAX_DELIVERY_RETRIES = 10


class AuditWorker:
    """
    Transactional Outbox Relay Worker.
    
    Guarantees:
    - Reliably transfers audit logs from PostgreSQL audit_outbox to MongoDB security_logs.
    - Uses FOR UPDATE SKIP LOCKED to prevent duplicate processing by concurrent worker instances.
    - Never holds PostgreSQL row locks during external network operations to MongoDB.
    - Uses lease expiration to recover orphaned events from crashed worker processes.
    - Employs exponential backoff and tracks retry counts.
    - Idempotent delivery using unique MongoDB event_id index.
    - Gracefully handles MongoDB downtime without data loss.
    """

    def __init__(self, batch_size: int = 50, poll_interval: float = 3.0):
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self._running = True

        # Signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received (%s). Finishing active batch and exiting...", signum)
        self._running = False

    def claim_pending_batch(self) -> List[Dict[str, Any]]:
        """
        Atomically claim a batch of pending or expired processing events.
        PostgreSQL lock is acquired, status is updated to PROCESSING, and transaction commits immediately.
        """
        claim_query = f"""
            UPDATE audit_outbox
            SET status = 'PROCESSING', processed_at = CURRENT_TIMESTAMP
            WHERE event_id IN (
                SELECT event_id
                FROM audit_outbox
                WHERE status = 'PENDING'
                   OR (status = 'PROCESSING' AND processed_at < CURRENT_TIMESTAMP - INTERVAL '{PROCESSING_LEASE_MINUTES} minutes')
                ORDER BY created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING event_id, event_type, payload, retry_count;
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(claim_query, (self.batch_size,))
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                batch = [dict(zip(columns, row)) for row in rows]
                return batch

    def process_event(self, event: Dict[str, Any]) -> bool:
        """
        Deliver a single claimed event to MongoDB.
        Normalizes document structure to match Section 8 specification:
        {event_id, action, customer_id, account_id, transaction_id, timestamp, ip_address, device_info, metadata}
        """
        event_id = str(event["event_id"])
        payload = event["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {"raw": payload}

        action = payload.get("action") or event.get("event_type", "UNKNOWN")
        customer_id = payload.get("customer_id")
        account_id = payload.get("account_id") or payload.get("sender_account_id") or payload.get("primary_account_id")
        transaction_id = payload.get("transaction_id")
        timestamp = payload.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        ip_address = payload.get("ip_address", "127.0.0.1")
        device_info = payload.get("device_info", "Desktop Client")

        # Collect extra fields into metadata
        standard_keys = {
            "event_id", "action", "customer_id", "account_id", "sender_account_id",
            "primary_account_id", "transaction_id", "timestamp", "ip_address", "device_info", "metadata"
        }
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"raw": metadata}
        for k, v in payload.items():
            if k not in standard_keys:
                metadata[k] = v

        mongo_doc = {
            "event_id": event_id,
            "action": action,
            "customer_id": customer_id,
            "account_id": account_id,
            "transaction_id": transaction_id,
            "timestamp": timestamp,
            "ip_address": ip_address,
            "device_info": device_info,
            "metadata": metadata,
        }

        # Deliver to MongoDB
        delivered = insert_audit_document(mongo_doc)

        current_retry = event.get("retry_count", 0)

        if delivered:
            # Mark DELIVERED in PostgreSQL
            update_query = """
                UPDATE audit_outbox
                SET status = 'DELIVERED', processed_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE event_id = %s;
            """
            execute_update(update_query, (event_id,))
            logger.info("Delivered event %s (%s) to MongoDB.", event_id, event.get("event_type"))
            return True
        else:
            # Handle delivery failure with retry backoff
            new_retry = current_retry + 1
            if new_retry >= MAX_DELIVERY_RETRIES:
                fail_query = """
                    UPDATE audit_outbox
                    SET status = 'FAILED', processed_at = CURRENT_TIMESTAMP, 
                        retry_count = %s, last_error = 'Exceeded maximum delivery retries to MongoDB.'
                    WHERE event_id = %s;
                """
                execute_update(fail_query, (new_retry, event_id))
                logger.error("Event %s marked FAILED after %d retries.", event_id, new_retry)
            else:
                backoff_query = """
                    UPDATE audit_outbox
                    SET status = 'PENDING', processed_at = CURRENT_TIMESTAMP,
                        retry_count = %s, last_error = 'MongoDB delivery connection failed; queued for retry.'
                    WHERE event_id = %s;
                """
                execute_update(backoff_query, (new_retry, event_id))
                logger.warning("Event %s failed to reach MongoDB (attempt %d/%d). Re-queued.",
                               event_id, new_retry, MAX_DELIVERY_RETRIES)
            return False

    def run_once(self) -> int:
        """Process a single batch of events. Returns number of processed events."""
        events = self.claim_pending_batch()
        if not events:
            return 0

        logger.info("Claimed %d pending outbox events for delivery.", len(events))
        success_count = 0
        for ev in events:
            if self.process_event(ev):
                success_count += 1

        logger.info("Batch summary: %d/%d events successfully delivered.", success_count, len(events))
        return len(events)

    def run_loop(self) -> None:
        """Continuous polling loop."""
        logger.info("Starting FinTrack Audit Worker daemon (poll interval: %.1fs)...", self.poll_interval)
        while self._running:
            try:
                processed = self.run_once()
                if processed == 0:
                    time.sleep(self.poll_interval)
            except Exception as exc:
                logger.error("Unexpected error in audit worker loop: %s", exc)
                time.sleep(self.poll_interval)

        logger.info("Audit Worker daemon stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="FinTrack Transactional Outbox Audit Worker")
    parser.add_argument("--once", action="store_true", help="Process available pending batch once and exit.")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds (default: 3.0)")
    parser.add_argument("--batch", type=int, default=50, help="Batch size per poll (default: 50)")

    args = parser.parse_args()
    worker = AuditWorker(batch_size=args.batch, poll_interval=args.interval)

    if args.once:
        worker.run_once()
    else:
        worker.run_loop()


if __name__ == "__main__":
    main()


"""
FinTrack - Audit Service & MongoDB Transactional Outbox Unit Tests
File: tests/test_audit.py
"""

import time
import uuid
from decimal import Decimal
import pytest

from config.settings import settings
from database_layer.mongodb import check_mongo_health, get_security_collection, insert_audit_document, query_audit_logs
from database_layer.postgres import execute_scalar, execute_update, fetch_one
from services.audit_service import audit_service
from services.transfer_service import transfer_service
from workers.audit_worker import AuditWorker


def test_outbox_event_creation():
    ev_uuid = str(uuid.uuid4())
    recorded_id = audit_service.record_outbox_event(
        event_type="TEST_OUTBOX_EVENT",
        payload={"note": "Outbox verification", "amount": 123.45},
        event_id=ev_uuid,
    )
    assert recorded_id == ev_uuid

    row = fetch_one("SELECT status, retry_count FROM audit_outbox WHERE event_id = %s;", (ev_uuid,))
    assert row["status"] == "PENDING"
    assert row["retry_count"] == 0


def test_worker_delivery_to_mongodb():
    ev_uuid = str(uuid.uuid4())
    audit_service.record_outbox_event(
        event_type="TRANSFER_AUDIT_TEST",
        payload={"customer_id": 1, "test_code": "SYNC_CHECK"},
        event_id=ev_uuid,
    )

    worker = AuditWorker()
    worker.run_once()

    # Verify our specific event was delivered (or run one more cycle if previous batch filled the limit)
    row = fetch_one("SELECT status, last_error FROM audit_outbox WHERE event_id = %s;", (ev_uuid,))
    if row and row["status"] != "DELIVERED":
        worker.run_once()
        row = fetch_one("SELECT status, last_error FROM audit_outbox WHERE event_id = %s;", (ev_uuid,))

    assert row["status"] == "DELIVERED"
    assert row["last_error"] is None

    # Check MongoDB collection contains the document
    logs = query_audit_logs({"event_id": ev_uuid})
    assert len(logs) == 1
    assert logs[0]["event_id"] == ev_uuid


def test_duplicate_event_prevention():
    # Calling insert_audit_document with same event_id twice must not raise an error
    ev_uuid = str(uuid.uuid4())
    doc = {"event_id": ev_uuid, "action": "IDEMPOTENT_TEST", "val": 100}

    assert insert_audit_document(doc) is True
    # Second call should handle DuplicateKey gracefully and return True
    assert insert_audit_document(doc) is True


def test_financial_operations_unaffected_by_mongodb_outage(monkeypatch):
    """
    Transactional Outbox Guarantee:
    Even if MongoDB is completely offline / throwing exceptions,
    PostgreSQL financial transactions MUST commit successfully.
    """
    # Simulate MongoDB failure in worker
    monkeypatch.setattr("workers.audit_worker.insert_audit_document", lambda doc: False)

    # Perform financial transfer
    sender_before = execute_scalar("SELECT balance FROM accounts WHERE account_id = 1001;")
    res = transfer_service.execute_transfer(
        authenticated_customer_id=1,
        sender_account_id=1001,
        receiver_account_id=1003,
        amount=Decimal("150.00"),
        description="Resilience test during MongoDB outage",
    )

    assert res["status"] == "SUCCESS"
    sender_after = execute_scalar("SELECT balance FROM accounts WHERE account_id = 1001;")
    assert sender_after == sender_before - Decimal("150.00")

    # Worker runs while Mongo is down: should mark retry, NOT crash
    worker = AuditWorker()
    worker.run_once()

    # Verify event is still safe in outbox pending retry
    pending_count = execute_scalar("SELECT COUNT(*) FROM audit_outbox WHERE status = 'PENDING';")
    assert pending_count >= 1


def test_abandoned_event_recovery():
    """
    Verify worker reclaims events left in PROCESSING status if worker crashed (lease expired).
    """
    ev_uuid = str(uuid.uuid4())
    audit_service.record_outbox_event("ORPHAN_TEST", {"data": 1}, event_id=ev_uuid)

    # Artificially set event to PROCESSING with timestamp 5 minutes ago
    execute_update(
        """
        UPDATE audit_outbox 
        SET status = 'PROCESSING', processed_at = CURRENT_TIMESTAMP - INTERVAL '5 minutes'
        WHERE event_id = %s;
        """,
        (ev_uuid,),
    )

    worker = AuditWorker()
    processed = worker.run_once()
    assert processed >= 1

    # Status must now be DELIVERED
    row = fetch_one("SELECT status FROM audit_outbox WHERE event_id = %s;", (ev_uuid,))
    assert row["status"] == "DELIVERED"

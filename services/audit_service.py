"""
FinTrack - Smart Digital Banking & Loan Management System
Audit Service - Transactional Outbox Pattern
File: services/audit_service.py
"""

import datetime
import json
import logging
from typing import Any, Dict, Optional, Union
import uuid
from psycopg2.extensions import connection as PgConnection

from database_layer.postgres import execute_update, transaction

logger = logging.getLogger(__name__)


class AuditService:
    """
    Manages audit event creation within PostgreSQL transactions.
    
    Adheres strictly to the Transactional Outbox Pattern:
    - Events are committed in the same database transaction as financial operations.
    - An asynchronous worker subsequently relays pending outbox events to MongoDB.
    - MongoDB failures can never roll back or block committed PostgreSQL transactions.
    """

    @staticmethod
    def record_outbox_event(
        event_type: str,
        payload: Dict[str, Any],
        conn: Optional[PgConnection] = None,
        event_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> str:
        """
        Record a sanitized security/financial event in the PostgreSQL `audit_outbox` table.

        Args:
            event_type: Action descriptor (e.g., 'LOGIN_SUCCESS', 'TRANSFER_SUCCESS', 'LOAN_APPLIED').
            payload: Event data dictionary (sanitized of sensitive passwords or tokens).
            conn: Active PostgreSQL connection participating in the current transaction.
            event_id: Optional specific UUID; otherwise a new UUID4 is generated.

        Returns:
            The string UUID of the recorded event.
        """
        event_uuid = str(event_id) if event_id else str(uuid.uuid4())
        sanitized_payload = AuditService._sanitize_payload(payload)

        # Ensure timestamp is recorded in payload
        if "timestamp" not in sanitized_payload:
            sanitized_payload["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sanitized_payload["event_id"] = event_uuid
        sanitized_payload["action"] = event_type

        query = """
            INSERT INTO audit_outbox (event_id, event_type, payload, status, retry_count, created_at)
            VALUES (%s, %s, %s::jsonb, 'PENDING', 0, CURRENT_TIMESTAMP);
        """

        payload_json = json.dumps(sanitized_payload, default=str)

        if conn is not None:
            # Execute within the caller's active transaction
            with conn.cursor() as cur:
                cur.execute(query, (event_uuid, event_type, payload_json))
        else:
            # Execute in a new standalone transaction
            with transaction() as standalone_conn:
                with standalone_conn.cursor() as cur:
                    cur.execute(query, (event_uuid, event_type, payload_json))

        logger.debug("Recorded audit outbox event: %s (%s)", event_uuid, event_type)
        return event_uuid

    @staticmethod
    def _sanitize_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively strip sensitive values (passwords, tokens, keys) from audit payloads.
        """
        sensitive_keys = {
            "password", "password_hash", "token", "secret", "cvv", "credit_card", "auth_token"
        }
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = AuditService._sanitize_payload(v)
            else:
                sanitized[k] = v
        return sanitized


audit_service = AuditService()


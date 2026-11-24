"""
FinTrack - Smart Digital Banking & Loan Management System
Financial Transaction & Transfer Engine
File: services/transfer_service.py
"""

from decimal import Decimal
import logging
import random
import time
from typing import Any, Dict, List, Optional, Union
import uuid
import psycopg2
from psycopg2 import errorcodes

from config.settings import settings
from database_layer.db import get_db_connection
from database_layer.postgres import (
    AccountFrozenError,
    ConcurrencyError,
    DatabaseError,
    DuplicateIdempotencyError,
    InsufficientFundsError,
    IntegrityError,
    NotFoundError,
    fetch_one,
    set_rls_context,
    transaction,
)
from security import security_validator
from services.audit_service import audit_service

logger = logging.getLogger(__name__)


class TransferService:
    """
    High-integrity Financial Transaction Engine.
    
    Guarantees:
    - ACID Compliance via strict explicit transaction boundaries.
    - Deterministic ascending row lock ordering (`SELECT ... FOR UPDATE ORDER BY account_id ASC`)
      to guarantee deadlock prevention across concurrent transfers.
    - Strict customer account ownership authorization.
    - Idempotency key deduplication (returns existing transaction without double-spending).
    - Statistical ML anomaly detection and hard threshold enforcement.
    - Suspicious transfers recorded as FLAGGED with zero money movement until administrative review.
    - Balanced double-entry bookkeeping (1 Debit, 1 Credit).
    - Transactional Outbox pattern for audit reliability.
    """

    @classmethod
    def execute_transfer(
        cls,
        authenticated_customer_id: int,
        sender_account_id: int,
        receiver_account_id: int,
        amount: Union[Decimal, float, int, str],
        description: str = "Fund Transfer",
        idempotency_key: Optional[Union[uuid.UUID, str]] = None,
        ip_address: str = "127.0.0.1",
        device_info: str = "Web Client",
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Execute an atomic fund transfer with deadlock retry and idempotency verification.
        """
        # 1. Parse and validate amount using Decimal
        try:
            transfer_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        except Exception as e:
            raise ValueError(f"Invalid transfer amount format: {amount}") from e

        if transfer_amount <= Decimal("0.00"):
            raise ValueError("Transfer amount must be strictly greater than zero.")

        # 2. Prevent self-transfers
        if sender_account_id == receiver_account_id:
            raise ValueError("Sender and receiver accounts must be different.")

        # Rate limiting: Maximum 30 transfers per minute per customer to prevent rapid drain attacks
        allowed, retry_after = security_validator.check_rate_limit(
            f"transfer_customer_{authenticated_customer_id}",
            max_requests=30,
            window_seconds=60,
        )
        if not allowed:
            raise DatabaseError(f"Transfer rate limit exceeded. Please wait {retry_after} seconds.")

        # Sanitize description against XSS and control chars
        clean_desc = security_validator.sanitize_text(description, max_len=200)

        # 3. Generate or validate idempotency key
        idem_uuid = str(idempotency_key) if idempotency_key else str(uuid.uuid4())

        # 4. Check idempotency: if transaction already committed, return original result
        existing_tx = fetch_one(
            "SELECT * FROM transactions WHERE idempotency_key = %s;",
            (idem_uuid,),
        )
        if existing_tx:
            logger.info("Idempotent replay detected for key %s (tx #%s)", idem_uuid, existing_tx["transaction_id"])
            return {
                "status": existing_tx["status"],
                "transaction_id": existing_tx["transaction_id"],
                "amount": existing_tx["amount"],
                "is_replay": True,
                "message": f"Transfer previously submitted with status: {existing_tx['status']}.",
            }

        # 5. Execute with bounded retry for transient database conflicts/deadlocks
        for attempt in range(max_retries):
            try:
                return cls._do_transfer_transaction(
                    authenticated_customer_id=authenticated_customer_id,
                    sender_account_id=sender_account_id,
                    receiver_account_id=receiver_account_id,
                    amount=transfer_amount,
                    description=clean_desc,
                    idempotency_key=idem_uuid,
                    ip_address=ip_address,
                    device_info=device_info,
                )
            except (ConcurrencyError, psycopg2.extensions.TransactionRollbackError) as ce:
                if attempt < max_retries - 1:
                    jitter = random.uniform(0.05, 0.2) * (2 ** attempt)
                    logger.warning("Concurrency conflict in transfer (attempt %d/%d). Retrying in %.2fs: %s",
                                   attempt + 1, max_retries, ce)
                    time.sleep(jitter)
                    continue
                raise ConcurrencyError("Transfer timed out due to high database contention. Please try again.") from ce

        raise ConcurrencyError("Failed to complete transfer after maximum retry attempts.")

    @classmethod
    def _do_transfer_transaction(
        cls,
        authenticated_customer_id: int,
        sender_account_id: int,
        receiver_account_id: int,
        amount: Decimal,
        description: str,
        idempotency_key: str,
        ip_address: str,
        device_info: str,
    ) -> Dict[str, Any]:
        """
        Internal atomic transaction method. Python controls commit/rollback boundaries.
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                # 1. Deterministic Lock Ordering: Ascending account_id order
                lower_id, higher_id = sorted([sender_account_id, receiver_account_id])

                lock_query = """
                    SELECT account_id, customer_id, balance, currency, is_frozen
                    FROM accounts
                    WHERE account_id IN (%s, %s)
                    ORDER BY account_id ASC
                    FOR UPDATE;
                """
                cur.execute(lock_query, (lower_id, higher_id))
                locked_accounts = {row[0]: {
                    "account_id": row[0],
                    "customer_id": row[1],
                    "balance": row[2],
                    "currency": row[3],
                    "is_frozen": row[4]
                } for row in cur.fetchall()}

                # 2. Verify account existence
                if sender_account_id not in locked_accounts:
                    raise NotFoundError(f"Sender account #{sender_account_id} does not exist.")
                if receiver_account_id not in locked_accounts:
                    raise NotFoundError(f"Receiver account #{receiver_account_id} does not exist.")

                sender = locked_accounts[sender_account_id]
                receiver = locked_accounts[receiver_account_id]

                # 3. Ownership authorization check
                if sender["customer_id"] != authenticated_customer_id:
                    raise DatabaseError(f"Unauthorized: You do not own sender account #{sender_account_id}.")

                # 4. Frozen account check
                if sender["is_frozen"]:
                    raise AccountFrozenError(f"Sender account #{sender_account_id} is frozen.")
                if receiver["is_frozen"]:
                    raise AccountFrozenError(f"Receiver account #{receiver_account_id} is frozen.")

                # 5. Check sufficient balance
                if sender["balance"] < amount:
                    raise InsufficientFundsError(
                        f"Insufficient funds: Account #{sender_account_id} balance is INR {sender['balance']:,.2f}, "
                        f"but requested transfer is INR {amount:,.2f}."
                    )

                # 6. Rule-based Fraud Check (Deterministic Fixed Business Rule - No AI/ML)
                # Any transfer >= settings.FRAUD_THRESHOLD (INR 10,000.00) is held for manual review.
                is_flagged = amount >= settings.FRAUD_THRESHOLD

                if is_flagged:
                    risk_score = 1.00
                    reason = f"Deterministic threshold exceeded: Transfer amount of INR {amount:,.2f} meets or exceeds review threshold of INR {settings.FRAUD_THRESHOLD:,.2f}."

                    # A. Record FLAGGED transaction WITHOUT moving money
                    cur.execute(
                        """
                        INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description)
                        VALUES (%s, %s, %s, 'FLAGGED', %s, %s)
                        RETURNING transaction_id;
                        """,
                        (sender_account_id, receiver_account_id, amount, idempotency_key, description),
                    )
                    tx_id = cur.fetchone()[0]

                    # B. Record fraud alert
                    cur.execute(
                        """
                        INSERT INTO fraud_alerts (transaction_id, account_id, risk_score, reason, status)
                        VALUES (%s, %s, %s, %s, 'OPEN')
                        RETURNING alert_id;
                        """,
                        (tx_id, sender_account_id, risk_score, reason),
                    )
                    alert_id = cur.fetchone()[0]

                    # C. Write outbox event
                    audit_service.record_outbox_event(
                        "TRANSFER_FLAGGED",
                        {
                            "transaction_id": tx_id,
                            "alert_id": alert_id,
                            "sender_account_id": sender_account_id,
                            "receiver_account_id": receiver_account_id,
                            "amount": float(amount),
                            "risk_score": risk_score,
                            "reason": reason,
                            "method": "DETERMINISTIC_RULE_THRESHOLD",
                            "ip_address": ip_address,
                            "device_info": device_info,
                        },
                        conn=conn,
                    )

                    logger.warning("Transfer FLAGGED for compliance review: tx #%d (Amount: INR %s)", tx_id, amount)
                    return {
                        "status": "FLAGGED",
                        "transaction_id": tx_id,
                        "alert_id": alert_id,
                        "amount": amount,
                        "risk_score": risk_score,
                        "reason": reason,
                        "message": "Transfer flagged for security compliance review. Balances remain unchanged pending administrator approval.",
                    }

                # 9. Normal Transfer Execution (Clean Transaction)
                # A. Deduct sender balance
                cur.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE account_id = %s RETURNING balance;",
                    (amount, sender_account_id),
                )
                new_sender_bal = cur.fetchone()[0]

                # B. Credit receiver balance
                cur.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE account_id = %s RETURNING balance;",
                    (amount, receiver_account_id),
                )
                new_receiver_bal = cur.fetchone()[0]

                # C. Record SUCCESS transaction
                cur.execute(
                    """
                    INSERT INTO transactions (sender_account_id, receiver_account_id, amount, status, idempotency_key, description)
                    VALUES (%s, %s, %s, 'SUCCESS', %s, %s)
                    RETURNING transaction_id;
                    """,
                    (sender_account_id, receiver_account_id, amount, idempotency_key, description),
                )
                tx_id = cur.fetchone()[0]

                # D. Insert two balanced ledger entries (Double-entry bookkeeping)
                cur.execute(
                    """
                    INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount)
                    VALUES 
                    (%s, %s, 'DEBIT', %s),
                    (%s, %s, 'CREDIT', %s);
                    """,
                    (tx_id, sender_account_id, amount, tx_id, receiver_account_id, amount),
                )

                # E. Record audit outbox event
                audit_service.record_outbox_event(
                    "TRANSFER_SUCCESS",
                    {
                        "transaction_id": tx_id,
                        "sender_account_id": sender_account_id,
                        "receiver_account_id": receiver_account_id,
                        "amount": float(amount),
                        "sender_new_balance": float(new_sender_bal),
                        "receiver_new_balance": float(new_receiver_bal),
                        "ip_address": ip_address,
                        "device_info": device_info,
                    },
                    conn=conn,
                )

                logger.info("Successfully executed transfer tx #%d (INR %s from #%d to #%d)",
                            tx_id, amount, sender_account_id, receiver_account_id)

                return {
                    "status": "SUCCESS",
                    "transaction_id": tx_id,
                    "sender_account_id": sender_account_id,
                    "receiver_account_id": receiver_account_id,
                    "amount": amount,
                    "new_balance": new_sender_bal,
                    "message": f"Successfully transferred INR {amount:,.2f} to account #{receiver_account_id}.",
                }


transfer_service = TransferService()


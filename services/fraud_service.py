"""
FinTrack - Smart Digital Banking & Loan Management System
Fraud Review & Flagged Transfer Management Service
File: services/fraud_service.py
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from database_layer.postgres import (
    AccountFrozenError,
    DatabaseError,
    InsufficientFundsError,
    NotFoundError,
    fetch_all,
    fetch_one,
    transaction,
)
from services.audit_service import audit_service

logger = logging.getLogger(__name__)


class FraudService:
    """Manages compliance monitoring, open fraud alerts, and administrator review workflows."""

    @staticmethod
    def get_fraud_alerts(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch fraud alerts using View_Fraud_Alerts.
        """
        if status_filter:
            query = "SELECT * FROM View_Fraud_Alerts WHERE alert_status = %s ORDER BY alert_created_at DESC;"
            return fetch_all(query, (status_filter,))
        query = "SELECT * FROM View_Fraud_Alerts ORDER BY alert_created_at DESC;"
        return fetch_all(query)

    @classmethod
    def review_flagged_transfer(
        cls,
        alert_id: int,
        admin_user_id: int,
        decision: str,  # 'APPROVE' or 'REJECT'
        admin_notes: str = "",
    ) -> Dict[str, Any]:
        """
        Process administrator decision on a flagged transaction.

        If APPROVE:
        - Re-locks both accounts in ascending order.
        - Re-validates account status and sufficient balance.
        - Atomically debits sender and credits receiver.
        - Generates 2 balanced double-entry ledger records.
        - Updates transaction status to SUCCESS.
        - Updates fraud_alerts status to APPROVED.

        If REJECT:
        - Updates transaction status to FAILED.
        - Updates fraud_alerts status to REJECTED.
        - Zero money movement.
        """
        decision_clean = decision.strip().upper()
        if decision_clean not in ("APPROVE", "REJECT"):
            raise ValueError("Decision must be either 'APPROVE' or 'REJECT'.")

        with transaction() as conn:
            with conn.cursor() as cur:
                # 1. Fetch and lock fraud alert record
                cur.execute(
                    """
                    SELECT fa.alert_id, fa.transaction_id, fa.account_id, fa.status,
                           t.sender_account_id, t.receiver_account_id, t.amount, t.status AS tx_status
                    FROM fraud_alerts fa
                    JOIN transactions t ON fa.transaction_id = t.transaction_id
                    WHERE fa.alert_id = %s
                    FOR UPDATE;
                    """,
                    (alert_id,),
                )
                alert_row = cur.fetchone()
                if not alert_row:
                    raise NotFoundError(f"Fraud alert #{alert_id} not found.")

                alert_id_val, tx_id, acc_id, alert_status, sender_id, receiver_id, amount, tx_status = alert_row

                if alert_status != "OPEN":
                    raise DatabaseError(f"Fraud alert #{alert_id} has already been reviewed (status: {alert_status}).")

                if decision_clean == "REJECT":
                    # Mark alert REJECTED and transaction FAILED without moving money
                    cur.execute(
                        """
                        UPDATE fraud_alerts 
                        SET status = 'REJECTED', reviewed_at = CURRENT_TIMESTAMP
                        WHERE alert_id = %s;
                        """,
                        (alert_id,),
                    )
                    cur.execute(
                        "UPDATE transactions SET status = 'FAILED' WHERE transaction_id = %s;",
                        (tx_id,),
                    )

                    audit_service.record_outbox_event(
                        "FRAUD_ALERT_REJECTED",
                        {
                            "alert_id": alert_id,
                            "transaction_id": tx_id,
                            "admin_user_id": admin_user_id,
                            "notes": admin_notes,
                            "amount": float(amount),
                        },
                        conn=conn,
                    )
                    logger.info("Admin %d REJECTED flagged transfer tx #%d", admin_user_id, tx_id)
                    return {
                        "status": "REJECTED",
                        "alert_id": alert_id,
                        "transaction_id": tx_id,
                        "message": f"Transfer tx #{tx_id} rejected. No funds were debited or credited.",
                    }

                # Decision is APPROVE: Re-lock accounts and execute atomic money movement
                lower_id, higher_id = sorted([sender_id, receiver_id])
                cur.execute(
                    """
                    SELECT account_id, balance, is_frozen
                    FROM accounts
                    WHERE account_id IN (%s, %s)
                    ORDER BY account_id ASC
                    FOR UPDATE;
                    """,
                    (lower_id, higher_id),
                )
                accounts_map = {row[0]: {"balance": row[1], "is_frozen": row[2]} for row in cur.fetchall()}

                if sender_id not in accounts_map or receiver_id not in accounts_map:
                    raise NotFoundError("One or both accounts no longer exist.")

                sender_acc = accounts_map[sender_id]
                receiver_acc = accounts_map[receiver_id]

                if sender_acc["is_frozen"]:
                    raise AccountFrozenError(f"Cannot approve: Sender account #{sender_id} is frozen.")
                if receiver_acc["is_frozen"]:
                    raise AccountFrozenError(f"Cannot approve: Receiver account #{receiver_id} is frozen.")

                if sender_acc["balance"] < amount:
                    raise InsufficientFundsError(
                        f"Cannot approve: Sender account #{sender_id} currently has insufficient balance "
                        f"(Available: INR {sender_acc['balance']:,.2f}, Required: INR {amount:,.2f})."
                    )

                # Move funds
                cur.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE account_id = %s;",
                    (amount, sender_id),
                )
                cur.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE account_id = %s;",
                    (amount, receiver_id),
                )

                # Update transaction status to SUCCESS
                cur.execute(
                    "UPDATE transactions SET status = 'SUCCESS' WHERE transaction_id = %s;",
                    (tx_id,),
                )

                # Insert balanced double-entry ledger entries
                cur.execute(
                    """
                    INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount)
                    VALUES 
                    (%s, %s, 'DEBIT', %s),
                    (%s, %s, 'CREDIT', %s);
                    """,
                    (tx_id, sender_id, amount, tx_id, receiver_id, amount),
                )

                # Mark fraud alert APPROVED
                cur.execute(
                    """
                    UPDATE fraud_alerts 
                    SET status = 'APPROVED', reviewed_at = CURRENT_TIMESTAMP
                    WHERE alert_id = %s;
                    """,
                    (alert_id,),
                )

                audit_service.record_outbox_event(
                    "FRAUD_ALERT_APPROVED",
                    {
                        "alert_id": alert_id,
                        "transaction_id": tx_id,
                        "admin_user_id": admin_user_id,
                        "amount": float(amount),
                        "sender_account_id": sender_id,
                        "receiver_account_id": receiver_id,
                        "notes": admin_notes,
                    },
                    conn=conn,
                )

                logger.info("Admin %d APPROVED flagged transfer tx #%d (INR %s transferred)",
                            admin_user_id, tx_id, amount)

                return {
                    "status": "APPROVED",
                    "alert_id": alert_id,
                    "transaction_id": tx_id,
                    "amount": amount,
                    "message": f"Flagged transfer #{tx_id} approved and executed successfully.",
                }


fraud_service = FraudService()


"""
FinTrack - Smart Digital Banking & Loan Management System
Account Management & Ledger Analysis Service
File: services/account_service.py
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from database_layer.postgres import (
    DatabaseError,
    NotFoundError,
    fetch_all,
    fetch_one,
)

logger = logging.getLogger(__name__)


class AccountService:
    """Manages customer account balances, ownership authorization, transactions and ledger history."""

    @staticmethod
    def get_customer_accounts(customer_id: int) -> List[Dict[str, Any]]:
        """
        Fetch all bank accounts belonging to a specific authenticated customer.
        Strict authorization safeguard: ensures customers can only view their own accounts.
        """
        query = """
            SELECT 
                account_id,
                customer_id,
                account_type,
                balance,
                currency,
                is_frozen,
                created_at,
                updated_at
            FROM accounts
            WHERE customer_id = %s
            ORDER BY account_id ASC;
        """
        return fetch_all(query, (customer_id,))

    @staticmethod
    def get_account_by_id(account_id: int, customer_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch account details. If customer_id is supplied, verifies strict ownership.
        """
        query = """
            SELECT 
                a.account_id,
                a.customer_id,
                c.full_name AS customer_name,
                c.email AS customer_email,
                a.account_type,
                a.balance,
                a.currency,
                a.is_frozen,
                a.created_at,
                a.updated_at
            FROM accounts a
            JOIN customers c ON a.customer_id = c.customer_id
            WHERE a.account_id = %s;
        """
        account = fetch_one(query, (account_id,))
        if not account:
            raise NotFoundError(f"Account #{account_id} not found.")

        if customer_id is not None and account["customer_id"] != customer_id:
            raise DatabaseError(f"Unauthorized: You do not own account #{account_id}.")

        return account

    @staticmethod
    def verify_account_ownership(account_id: int, customer_id: int) -> bool:
        """Verify whether an account belongs to a given customer."""
        query = "SELECT 1 FROM accounts WHERE account_id = %s AND customer_id = %s;"
        return bool(fetch_one(query, (account_id, customer_id)))

    @staticmethod
    def get_account_recent_transactions(account_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch recent transactions (incoming and outgoing) for a specific account.
        """
        query = """
            SELECT 
                t.transaction_id,
                t.idempotency_key,
                t.sender_account_id,
                sc.full_name AS sender_name,
                t.receiver_account_id,
                rc.full_name AS receiver_name,
                t.amount,
                sa.currency,
                t.status,
                t.description,
                t.transaction_date,
                CASE 
                    WHEN t.sender_account_id = %s THEN 'DEBIT'
                    ELSE 'CREDIT'
                END AS direction
            FROM transactions t
            JOIN accounts sa ON t.sender_account_id = sa.account_id
            JOIN customers sc ON sa.customer_id = sc.customer_id
            JOIN accounts ra ON t.receiver_account_id = ra.account_id
            JOIN customers rc ON ra.customer_id = rc.customer_id
            WHERE t.sender_account_id = %s OR t.receiver_account_id = %s
            ORDER BY t.transaction_date DESC, t.transaction_id DESC
            LIMIT %s;
        """
        return fetch_all(query, (account_id, account_id, account_id, limit))

    @staticmethod
    def get_running_balance(account_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Calculate running account balance using Advanced SQL Query 1 (Window Functions).
        """
        query = """
            SELECT 
                entry_id,
                account_id,
                entry_type,
                amount,
                created_at,
                SUM(CASE WHEN entry_type = 'CREDIT' THEN amount ELSE -amount END) 
                    OVER (PARTITION BY account_id ORDER BY created_at ASC, entry_id ASC) AS running_balance
            FROM ledger_entries
            WHERE account_id = %s
            ORDER BY created_at DESC, entry_id DESC
            LIMIT %s;
        """
        return fetch_all(query, (account_id, limit))

    @staticmethod
    def get_monthly_spending_analysis(account_id: int) -> List[Dict[str, Any]]:
        """
        Calculate monthly outgoing spending using Advanced SQL Query 2 (Common Table Expression).
        """
        query = """
            WITH monthly_outgoing AS (
                SELECT 
                    sender_account_id AS account_id,
                    DATE_TRUNC('month', transaction_date) AS month_start,
                    SUM(amount) AS total_monthly_outgoing,
                    COUNT(transaction_id) AS transfer_count
                FROM transactions
                WHERE sender_account_id = %s AND status = 'SUCCESS'
                GROUP BY sender_account_id, DATE_TRUNC('month', transaction_date)
            )
            SELECT 
                TO_CHAR(month_start, 'YYYY-MM') AS month_label,
                total_monthly_outgoing,
                transfer_count
            FROM monthly_outgoing
            ORDER BY month_label ASC;
        """
        return fetch_all(query, (account_id,))

    @staticmethod
    def get_account_summary_metrics(account_id: int) -> Dict[str, Any]:
        """
        Retrieve account summary metrics from View_Account_Summary.
        """
        query = "SELECT * FROM View_Account_Summary WHERE account_id = %s;"
        summary = fetch_one(query, (account_id,))
        if not summary:
            raise NotFoundError(f"Summary for account #{account_id} not found.")
        return summary


account_service = AccountService()

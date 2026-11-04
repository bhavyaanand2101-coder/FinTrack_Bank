"""
FinTrack - Smart Digital Banking & Loan Management System
Loan Application & Credit Decisioning Service
File: services/loan_service.py
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from database_layer.postgres import (
    DatabaseError,
    NotFoundError,
    fetch_all,
    fetch_one,
    transaction,
)
from services.audit_service import audit_service

logger = logging.getLogger(__name__)


class LoanService:
    """Manages loan applications, credit calculations, and administrator decision workflows."""

    @staticmethod
    def calculate_eligibility(
        annual_income: Union[Decimal, float, int],
        requested_amount: Union[Decimal, float, int],
        credit_score: int,
    ) -> Dict[str, Any]:
        """
        Evaluate loan eligibility based on income, debt-to-income limits, and credit tiering.
        Rules match database View_Loan_Eligibility:
        - Max Loan = 50% of annual income.
        - Minimum credit score: 650.
        """
        income_dec = Decimal(str(annual_income))
        amount_dec = Decimal(str(requested_amount))

        if income_dec <= Decimal("0"):
            raise ValueError("Annual income must be greater than zero.")
        if amount_dec <= Decimal("0"):
            raise ValueError("Requested loan amount must be greater than zero.")
        if not (300 <= credit_score <= 900):
            raise ValueError("Credit score must be between 300 and 900.")

        max_allowed = (income_dec * Decimal("0.50")).quantize(Decimal("0.01"))

        if credit_score >= 800:
            suggested_rate = Decimal("7.50")
            status = "PRE-APPROVED" if amount_dec <= max_allowed else "EXCEEDS_LIMIT"
        elif credit_score >= 750:
            suggested_rate = Decimal("8.75")
            status = "PRE-APPROVED" if amount_dec <= max_allowed else "EXCEEDS_LIMIT"
        elif credit_score >= 700:
            suggested_rate = Decimal("10.50")
            status = "ELIGIBLE" if amount_dec <= max_allowed else "EXCEEDS_LIMIT"
        elif credit_score >= 650:
            suggested_rate = Decimal("12.00")
            status = "ELIGIBLE" if amount_dec <= max_allowed else "EXCEEDS_LIMIT"
        else:
            suggested_rate = Decimal("15.00")
            status = "INELIGIBLE_LOW_CREDIT"

        is_eligible = status in ("PRE-APPROVED", "ELIGIBLE") and amount_dec <= max_allowed

        return {
            "is_eligible": is_eligible,
            "status": status,
            "max_eligible_amount": max_allowed,
            "suggested_interest_rate": suggested_rate,
            "requested_amount": amount_dec,
            "annual_income": income_dec,
            "credit_score": credit_score,
        }

    @classmethod
    def apply_for_loan(
        cls,
        customer_id: int,
        requested_amount: Union[Decimal, float, int],
        annual_income: Union[Decimal, float, int],
        credit_score: int,
    ) -> Dict[str, Any]:
        """
        Submit a new loan application.
        """
        eval_result = cls.calculate_eligibility(annual_income, requested_amount, credit_score)

        query = """
            INSERT INTO loans (
                customer_id, requested_amount, annual_income, credit_score, 
                interest_rate, status, applied_at
            )
            VALUES (%s, %s, %s, %s, %s, 'PENDING', CURRENT_TIMESTAMP)
            RETURNING loan_id, applied_at;
        """

        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        customer_id,
                        eval_result["requested_amount"],
                        eval_result["annual_income"],
                        credit_score,
                        eval_result["suggested_interest_rate"],
                    ),
                )
                row = cur.fetchone()
                loan_id = row[0]
                applied_at = row[1]

            audit_service.record_outbox_event(
                "LOAN_APPLICATION_SUBMITTED",
                {
                    "loan_id": loan_id,
                    "customer_id": customer_id,
                    "requested_amount": float(eval_result["requested_amount"]),
                    "annual_income": float(eval_result["annual_income"]),
                    "credit_score": credit_score,
                    "suggested_interest_rate": float(eval_result["suggested_interest_rate"]),
                    "pre_check_eligible": eval_result["is_eligible"],
                },
                conn=conn,
            )

        logger.info("Submitted loan application #%d for customer %d", loan_id, customer_id)
        return {
            "loan_id": loan_id,
            "customer_id": customer_id,
            "requested_amount": eval_result["requested_amount"],
            "interest_rate": eval_result["suggested_interest_rate"],
            "is_eligible": eval_result["is_eligible"],
            "applied_at": applied_at,
            "status": "PENDING",
            "message": "Loan application successfully submitted and queued for administrator review.",
        }

    @staticmethod
    def get_customer_loans(customer_id: int) -> List[Dict[str, Any]]:
        """Fetch all loan applications submitted by a customer."""
        query = """
            SELECT 
                l.loan_id,
                l.customer_id,
                l.requested_amount,
                l.annual_income,
                l.credit_score,
                l.interest_rate,
                l.status,
                l.applied_at,
                l.reviewed_at,
                u.username AS reviewer_username
            FROM loans l
            LEFT JOIN users u ON l.reviewed_by = u.user_id
            WHERE l.customer_id = %s
            ORDER BY l.applied_at DESC;
        """
        return fetch_all(query, (customer_id,))

    @staticmethod
    def get_all_loans(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch loan applications for admin review."""
        if status_filter:
            query = """
                SELECT 
                    l.loan_id,
                    l.customer_id,
                    c.full_name AS customer_name,
                    c.email AS customer_email,
                    l.requested_amount,
                    l.annual_income,
                    l.credit_score,
                    l.interest_rate,
                    l.status,
                    l.applied_at,
                    l.reviewed_at,
                    u.username AS reviewer_username
                FROM loans l
                JOIN customers c ON l.customer_id = c.customer_id
                LEFT JOIN users u ON l.reviewed_by = u.user_id
                WHERE l.status = %s
                ORDER BY l.applied_at DESC;
            """
            return fetch_all(query, (status_filter,))
        else:
            query = """
                SELECT 
                    l.loan_id,
                    l.customer_id,
                    c.full_name AS customer_name,
                    c.email AS customer_email,
                    l.requested_amount,
                    l.annual_income,
                    l.credit_score,
                    l.interest_rate,
                    l.status,
                    l.applied_at,
                    l.reviewed_at,
                    u.username AS reviewer_username
                FROM loans l
                JOIN customers c ON l.customer_id = c.customer_id
                LEFT JOIN users u ON l.reviewed_by = u.user_id
                ORDER BY l.applied_at DESC;
            """
            return fetch_all(query)

    @classmethod
    def review_loan(
        cls,
        loan_id: int,
        admin_user_id: int,
        decision: str,  # 'APPROVED' or 'REJECTED'
    ) -> Dict[str, Any]:
        """
        Admin review: approve or reject a loan application under a database transaction.
        """
        decision_clean = decision.strip().upper()
        if decision_clean not in ("APPROVED", "REJECTED"):
            raise ValueError("Decision must be either 'APPROVED' or 'REJECTED'.")

        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT loan_id, customer_id, requested_amount, status FROM loans WHERE loan_id = %s FOR UPDATE;",
                    (loan_id,),
                )
                loan = cur.fetchone()
                if not loan:
                    raise NotFoundError(f"Loan application #{loan_id} not found.")

                loan_id_val, customer_id, requested_amount, status = loan

                if status != "PENDING":
                    raise DatabaseError(f"Loan application #{loan_id} has already been reviewed (status: {status}).")

                cur.execute(
                    """
                    UPDATE loans 
                    SET status = %s, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = %s
                    WHERE loan_id = %s;
                    """,
                    (decision_clean, admin_user_id, loan_id),
                )

            audit_service.record_outbox_event(
                "LOAN_DECISION",
                {
                    "loan_id": loan_id,
                    "customer_id": customer_id,
                    "admin_user_id": admin_user_id,
                    "decision": decision_clean,
                    "requested_amount": float(requested_amount),
                },
                conn=conn,
            )

        logger.info("Admin %d reviewed loan #%d: %s", admin_user_id, loan_id, decision_clean)
        return {
            "loan_id": loan_id,
            "status": decision_clean,
            "message": f"Loan application #{loan_id} {decision_clean.lower()} successfully.",
        }


loan_service = LoanService()


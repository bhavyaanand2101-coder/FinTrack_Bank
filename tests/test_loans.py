"""
FinTrack - Loan Service and Credit Eligibility Unit Tests
File: tests/test_loans.py
"""

from decimal import Decimal
import pytest

from database_layer.postgres import DatabaseError, NotFoundError
from services.loan_service import loan_service


def test_loan_eligibility_calculator():
    # 1. High credit score, within 50% income
    res1 = loan_service.calculate_eligibility(
        annual_income=800000.0,
        requested_amount=200000.0,
        credit_score=810,
    )
    assert res1["is_eligible"] is True
    assert res1["status"] == "PRE-APPROVED"
    assert res1["suggested_interest_rate"] == Decimal("7.50")
    assert res1["max_eligible_amount"] == Decimal("400000.00")

    # 2. Exceeds 50% income limit
    res2 = loan_service.calculate_eligibility(
        annual_income=400000.0,
        requested_amount=300000.0,  # Max allowed is 200,000
        credit_score=750,
    )
    assert res2["is_eligible"] is False
    assert res2["status"] == "EXCEEDS_LIMIT"

    # 3. Poor credit score (< 650)
    res3 = loan_service.calculate_eligibility(
        annual_income=600000.0,
        requested_amount=50000.0,
        credit_score=550,
    )
    assert res3["is_eligible"] is False
    assert res3["status"] == "INELIGIBLE_LOW_CREDIT"
    assert res3["suggested_interest_rate"] == Decimal("15.00")


def test_loan_input_validations():
    with pytest.raises(ValueError, match="income must be greater than zero"):
        loan_service.calculate_eligibility(-50000, 10000, 700)

    with pytest.raises(ValueError, match="amount must be greater than zero"):
        loan_service.calculate_eligibility(500000, 0, 700)

    with pytest.raises(ValueError, match="between 300 and 900"):
        loan_service.calculate_eligibility(500000, 50000, 950)


def test_loan_application_workflow():
    # Customer 1 submits loan application
    app_res = loan_service.apply_for_loan(
        customer_id=1,
        requested_amount=Decimal("75000.00"),
        annual_income=Decimal("700000.00"),
        credit_score=760,
    )

    loan_id = app_res["loan_id"]
    assert loan_id > 0
    assert app_res["status"] == "PENDING"

    # Admin approves the loan
    review_res = loan_service.review_loan(
        loan_id=loan_id,
        admin_user_id=1,
        decision="APPROVED",
    )
    assert review_res["status"] == "APPROVED"

    # Re-decisioning should be rejected
    with pytest.raises(DatabaseError, match="already been reviewed"):
        loan_service.review_loan(loan_id=loan_id, admin_user_id=1, decision="REJECTED")


def test_loan_application_rejection():
    app_res = loan_service.apply_for_loan(
        customer_id=2,
        requested_amount=Decimal("500000.00"),
        annual_income=Decimal("300000.00"),
        credit_score=590,
    )
    loan_id = app_res["loan_id"]

    review_res = loan_service.review_loan(
        loan_id=loan_id,
        admin_user_id=1,
        decision="REJECTED",
    )
    assert review_res["status"] == "REJECTED"


"""
FinTrack - Loan Management API Endpoints
File: api/routes/loans.py
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_user, require_admin, require_customer
from api.schemas import (
    AdminDecisionRequest,
    GenericMessageResponse,
    LoanApplyRequest,
    LoanCalculateRequest,
    LoanCalculateResponse,
    LoanOut,
)
from database_layer.postgres import DatabaseError, NotFoundError
from services.auth_service import AuthUser
from services.loan_service import LoanService

router = APIRouter(prefix="/api/loans", tags=["Loans"])


@router.post("/calculate", response_model=LoanCalculateResponse)
def calculate_loan_eligibility(
    req: LoanCalculateRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Calculate instant loan eligibility preview based on deterministic business rules."""
    try:
        result = LoanService.calculate_eligibility(
            annual_income=req.annual_income,
            requested_amount=req.requested_amount,
            credit_score=req.credit_score,
        )
        return LoanCalculateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def apply_for_loan(
    req: LoanApplyRequest,
    user: AuthUser = Depends(require_customer),
):
    """Submit a loan application for the authenticated customer."""
    try:
        app_res = LoanService.apply_for_loan(
            customer_id=user.customer_id,
            requested_amount=req.requested_amount,
            annual_income=req.annual_income,
            credit_score=req.credit_score,
        )
        # Fetch the created loan with customer info
        loans = LoanService.get_customer_loans(user.customer_id)
        matching = [l for l in loans if l["loan_id"] == app_res["loan_id"]]
        if matching:
            return matching[0]
        return app_res
    except (ValueError, DatabaseError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[LoanOut])
def get_customer_loans(user: AuthUser = Depends(get_current_user)):
    """Fetch loan applications. Customers see own; admins see all."""
    if user.is_customer():
        return LoanService.get_customer_loans(user.customer_id)
    return LoanService.get_all_loans()


# ---------------------------------------------------------------------------
# Admin Loan Review Routes
# ---------------------------------------------------------------------------

admin_loan_router = APIRouter(prefix="/api/admin/loans", tags=["Admin Loans"])


@admin_loan_router.get("", response_model=List[LoanOut])
def get_admin_loans(
    status_filter: Optional[str] = Query(default=None),
    admin: AuthUser = Depends(require_admin),
):
    """Fetch all loan applications for administrator review."""
    return LoanService.get_all_loans(status_filter=status_filter)


@admin_loan_router.patch("/{loan_id}/approve", response_model=GenericMessageResponse)
def approve_loan(
    loan_id: int,
    admin: AuthUser = Depends(require_admin),
):
    """Approve a pending loan application."""
    try:
        res = LoanService.review_loan(loan_id=loan_id, admin_user_id=admin.user_id, decision="APPROVED")
        return GenericMessageResponse(success=True, message=res["message"])
    except (NotFoundError, DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@admin_loan_router.patch("/{loan_id}/reject", response_model=GenericMessageResponse)
def reject_loan(
    loan_id: int,
    admin: AuthUser = Depends(require_admin),
):
    """Reject a pending loan application."""
    try:
        res = LoanService.review_loan(loan_id=loan_id, admin_user_id=admin.user_id, decision="REJECTED")
        return GenericMessageResponse(success=True, message=res["message"])
    except (NotFoundError, DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


"""
FinTrack - Fraud Review & Compliance API Endpoints
File: api/routes/fraud.py
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import require_admin
from api.schemas import (
    AdminDecisionRequest,
    FraudAlertOut,
    GenericMessageResponse,
)
from database_layer.postgres import (
    AccountFrozenError,
    DatabaseError,
    InsufficientFundsError,
    NotFoundError,
)
from services.auth_service import AuthUser
from services.fraud_service import FraudService

router = APIRouter(prefix="/api/admin/fraud-alerts", tags=["Admin Fraud"])


@router.get("", response_model=List[FraudAlertOut])
def get_fraud_alerts(
    status_filter: Optional[str] = Query(default=None),
    admin: AuthUser = Depends(require_admin),
):
    """Retrieve rule-flagged transfers from View_Fraud_Alerts."""
    return FraudService.get_fraud_alerts(status_filter=status_filter)


@router.patch("/{alert_id}/approve", response_model=GenericMessageResponse)
def approve_flagged_transfer(
    alert_id: int,
    req: Optional[AdminDecisionRequest] = None,
    admin: AuthUser = Depends(require_admin),
):
    """
    Approve flagged transfer.
    Atomically revalidates both accounts, executes fund movement, and commits balanced double-entry ledger entries.
    """
    notes = req.notes if req else ""
    try:
        res = FraudService.review_flagged_transfer(
            alert_id=alert_id,
            admin_user_id=admin.user_id,
            decision="APPROVE",
            admin_notes=notes,
        )
        return GenericMessageResponse(success=True, message=res["message"])
    except (InsufficientFundsError, AccountFrozenError, NotFoundError, DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{alert_id}/reject", response_model=GenericMessageResponse)
def reject_flagged_transfer(
    alert_id: int,
    req: Optional[AdminDecisionRequest] = None,
    admin: AuthUser = Depends(require_admin),
):
    """
    Reject flagged transfer.
    Marks transaction FAILED with zero money movement.
    """
    notes = req.notes if req else ""
    try:
        res = FraudService.review_flagged_transfer(
            alert_id=alert_id,
            admin_user_id=admin.user_id,
            decision="REJECT",
            admin_notes=notes,
        )
        return GenericMessageResponse(success=True, message=res["message"])
    except (NotFoundError, DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


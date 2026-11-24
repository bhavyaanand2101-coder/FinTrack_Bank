"""
FinTrack - Customer Accounts API Endpoints
File: api/routes/accounts.py
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.deps import get_current_user
from api.schemas import (
    AccountOut,
    AccountSummaryOut,
    MonthlySpendingItem,
    RunningBalanceEntry,
    TransactionOut,
)
from database_layer.postgres import DatabaseError, NotFoundError, fetch_all
from services.account_service import AccountService
from services.auth_service import AuthUser
from services.excel_service import ExcelService

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


@router.get("", response_model=List[AccountOut])
def get_accounts(user: AuthUser = Depends(get_current_user)):
    """
    Fetch bank accounts.
    If Customer: returns only accounts belonging to this customer.
    If Admin: returns all accounts across the bank.
    """
    if user.is_customer():
        if user.customer_id is None:
            raise HTTPException(status_code=400, detail="User missing customer ID.")
        accounts = AccountService.get_customer_accounts(user.customer_id)
    else:
        accounts = fetch_all(
            "SELECT account_id, customer_id, account_type, balance, currency, is_frozen, created_at, updated_at FROM accounts ORDER BY account_id ASC;"
        )
    return accounts


@router.get("/export-excel")
def export_my_excel(user: AuthUser = Depends(get_current_user)):
    """
    Download a personal live Excel workbook (.xlsx) of the authenticated user's data.
    Customers get only their own accounts, transactions, and loans. Admins get the full database.
    """
    try:
        if user.is_admin():
            excel_bytes = ExcelService.build_full_workbook_bytes()
            filename = "FinTrack_Live_Database.xlsx"
        else:
            if user.customer_id is None:
                raise HTTPException(status_code=400, detail="User missing customer ID.")
            excel_bytes = ExcelService.build_customer_workbook_bytes(user.customer_id)
            filename = f"FinTrack_{user.username}_Statement.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel export: {e}",
        )


@router.get("/{account_id}", response_model=AccountOut)
def get_account_detail(account_id: int, user: AuthUser = Depends(get_current_user)):
    """Fetch details for a specific bank account. Enforces IDOR authorization."""
    try:
        cust_id = user.customer_id if user.is_customer() else None
        account = AccountService.get_account_by_id(account_id, customer_id=cust_id)
        return account
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{account_id}/balance")
def get_account_balance(account_id: int, user: AuthUser = Depends(get_current_user)):
    """Get real-time balance for an account."""
    cust_id = user.customer_id if user.is_customer() else None
    try:
        account = AccountService.get_account_by_id(account_id, customer_id=cust_id)
        return {
            "account_id": account["account_id"],
            "balance": account["balance"],
            "currency": account["currency"],
            "is_frozen": account["is_frozen"],
            "account_type": account["account_type"],
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{account_id}/summary", response_model=AccountSummaryOut)
def get_account_summary(account_id: int, user: AuthUser = Depends(get_current_user)):
    """Get account metrics from View_Account_Summary."""
    cust_id = user.customer_id if user.is_customer() else None
    try:
        summary = AccountService.get_account_summary_metrics(account_id, customer_id=cust_id)
        return summary
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{account_id}/statement")
def get_account_statement(
    account_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    user: AuthUser = Depends(get_current_user),
):
    """
    Get full account statement:
    - Recent transactions
    - Running balance calculated via SQL Window Functions (Advanced Query 1)
    - Monthly spending breakdown via Common Table Expression (Advanced Query 2)
    """
    cust_id = user.customer_id if user.is_customer() else None
    try:
        # Verify ownership
        account = AccountService.get_account_by_id(account_id, customer_id=cust_id)
        transactions = AccountService.get_account_recent_transactions(account_id, limit=limit, customer_id=cust_id)
        running_balance = AccountService.get_running_balance(account_id, limit=limit, customer_id=cust_id)
        monthly_spending = AccountService.get_monthly_spending_analysis(account_id, customer_id=cust_id)

        return {
            "account": account,
            "transactions": transactions,
            "running_balance": running_balance,
            "monthly_spending": monthly_spending,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


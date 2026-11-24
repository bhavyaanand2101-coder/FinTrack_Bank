"""
FinTrack - Administration & Analytical Reports API Endpoints
File: api/routes/admin.py
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.deps import require_admin
from api.schemas import (
    AdminDashboardKPIs,
    CustomerDetailOut,
    FreezeAccountRequest,
    GenericMessageResponse,
    TransactionOut,
)
from database_layer.postgres import (
    DatabaseError,
    NotFoundError,
    execute_scalar,
    fetch_all,
    fetch_one,
)
from services.account_service import AccountService
from services.auth_service import AuthUser
from services.excel_service import ExcelService

router = APIRouter(prefix="/api/admin", tags=["Admin Operations"])


@router.get("/dashboard", response_model=AdminDashboardKPIs)
def get_admin_dashboard_kpis(admin: AuthUser = Depends(require_admin)):
    """Retrieve top KPIs and operational counters across the bank."""
    total_customers = execute_scalar("SELECT COUNT(*) FROM customers;") or 0
    total_accounts = execute_scalar("SELECT COUNT(*) FROM accounts;") or 0
    total_transactions = execute_scalar("SELECT COUNT(*) FROM transactions;") or 0
    total_volume = execute_scalar(
        "SELECT COALESCE(SUM(amount), 0.00) FROM transactions WHERE status = 'SUCCESS';"
    ) or Decimal("0.00")
    pending_loans = execute_scalar("SELECT COUNT(*) FROM loans WHERE status = 'PENDING';") or 0
    pending_fraud_reviews = execute_scalar("SELECT COUNT(*) FROM fraud_alerts WHERE status = 'OPEN';") or 0

    return AdminDashboardKPIs(
        total_customers=total_customers,
        total_accounts=total_accounts,
        total_transactions=total_transactions,
        total_volume=Decimal(str(total_volume)),
        pending_loans=pending_loans,
        pending_fraud_reviews=pending_fraud_reviews,
    )


@router.get("/customers", response_model=List[CustomerDetailOut])
def get_customers(
    search: Optional[str] = Query(default=None),
    admin: AuthUser = Depends(require_admin),
):
    """List all registered bank customers along with their associated accounts."""
    if search:
        query = """
            SELECT customer_id, full_name, email, phone, created_at
            FROM customers
            WHERE full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s
            ORDER BY customer_id ASC;
        """
        term = f"%{search}%"
        customers = fetch_all(query, (term, term, term))
    else:
        query = "SELECT customer_id, full_name, email, phone, created_at FROM customers ORDER BY customer_id ASC;"
        customers = fetch_all(query)

    # Attach accounts for each customer
    all_accounts = fetch_all(
        "SELECT account_id, customer_id, account_type, balance, currency, is_frozen, created_at, updated_at FROM accounts ORDER BY account_id ASC;"
    )
    acc_map: Dict[int, List[Dict[str, Any]]] = {}
    for acc in all_accounts:
        acc_map.setdefault(acc["customer_id"], []).append(acc)

    result = []
    for c in customers:
        c_copy = dict(c)
        c_copy["accounts"] = acc_map.get(c["customer_id"], [])
        result.append(c_copy)

    return result


@router.patch("/accounts/{account_id}/freeze", response_model=GenericMessageResponse)
def toggle_account_freeze(
    account_id: int,
    req: FreezeAccountRequest,
    admin: AuthUser = Depends(require_admin),
):
    """Freeze or unfreeze a customer account with audit outbox record."""
    try:
        AccountService.toggle_account_freeze(
            account_id=account_id,
            freeze=req.freeze,
            admin_user_id=admin.user_id,
        )
        action_word = "frozen" if req.freeze else "unfrozen"
        return GenericMessageResponse(
            success=True,
            message=f"Account #{account_id} has been successfully {action_word}.",
        )
    except (NotFoundError, DatabaseError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/transactions", response_model=List[TransactionOut])
def get_all_transactions(
    status_filter: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin: AuthUser = Depends(require_admin),
):
    """Monitor all transactions across the bank."""
    params: List[Any] = []
    where_sql = ""
    if status_filter:
        where_sql = "WHERE t.status = %s"
        params.append(status_filter.upper())

    query = f"""
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
            t.transaction_date
        FROM transactions t
        JOIN accounts sa ON t.sender_account_id = sa.account_id
        JOIN customers sc ON sa.customer_id = sc.customer_id
        JOIN accounts ra ON t.receiver_account_id = ra.account_id
        JOIN customers rc ON ra.customer_id = rc.customer_id
        {where_sql}
        ORDER BY t.transaction_date DESC, t.transaction_id DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


@router.get("/reports")
def get_advanced_reports(admin: AuthUser = Depends(require_admin)):
    """
    Generate Advanced DBMS analytical reports:
    1. Top 5 customers by transaction volume (Advanced Query 4: Subquery + Group By)
    2. Dormant accounts detection (Advanced Query 5: LEFT JOIN where tx count = 0)
    3. Monthly system transaction volume (Advanced Query 2: CTE)
    4. Account summary overview from View_Account_Summary
    """
    # 1. Top 5 Customers (Query 4)
    top_customers_query = """
        SELECT 
            c.customer_id,
            c.full_name,
            c.email,
            COUNT(t.transaction_id) AS total_transfers_sent,
            COALESCE(SUM(t.amount), 0.00) AS total_amount_transferred
        FROM customers c
        JOIN accounts a ON c.customer_id = a.customer_id
        JOIN transactions t ON a.account_id = t.sender_account_id
        WHERE t.status = 'SUCCESS'
        GROUP BY c.customer_id, c.full_name, c.email
        ORDER BY total_amount_transferred DESC
        LIMIT 5;
    """
    top_customers = fetch_all(top_customers_query)

    # 2. Dormant Accounts (Query 5)
    dormant_accounts_query = """
        SELECT 
            a.account_id,
            c.full_name AS customer_name,
            c.email AS customer_email,
            a.account_type,
            a.balance,
            a.created_at
        FROM accounts a
        JOIN customers c ON a.customer_id = c.customer_id
        LEFT JOIN transactions t 
            ON (a.account_id = t.sender_account_id OR a.account_id = t.receiver_account_id)
        WHERE t.transaction_id IS NULL
        ORDER BY a.created_at ASC;
    """
    dormant_accounts = fetch_all(dormant_accounts_query)

    # 3. Monthly Volume CTE (Query 2)
    monthly_volume_query = """
        WITH monthly_metrics AS (
            SELECT 
                DATE_TRUNC('month', transaction_date) AS month_start,
                COUNT(transaction_id) AS transfer_count,
                COALESCE(SUM(amount), 0.00) AS total_volume
            FROM transactions
            WHERE status = 'SUCCESS'
            GROUP BY DATE_TRUNC('month', transaction_date)
        )
        SELECT 
            TO_CHAR(month_start, 'YYYY-MM') AS month_label,
            transfer_count,
            total_volume
        FROM monthly_metrics
        ORDER BY month_label ASC;
    """
    monthly_volume = fetch_all(monthly_volume_query)

    # 4. View_Account_Summary sample
    summary_overview = fetch_all("SELECT * FROM View_Account_Summary LIMIT 10;")

    return {
        "top_customers": top_customers,
        "dormant_accounts": dormant_accounts,
        "monthly_volume": monthly_volume,
        "account_summaries": summary_overview,
    }


@router.get("/excel-status")
def get_excel_sync_status(admin: AuthUser = Depends(require_admin)):
    """Return status and last-updated timestamp of the live auto-synced Excel workbook."""
    return ExcelService.get_live_file_status()


@router.get("/export-excel")
def export_full_database_excel(admin: AuthUser = Depends(require_admin)):
    """
    Generate and download a live multi-sheet Excel workbook (.xlsx) of all database tables.
    Also refreshes `fintrack_live_data.xlsx` atomically on disk.
    """
    try:
        excel_bytes = ExcelService.build_full_workbook_bytes()
        # Keep local file synchronized as well
        ExcelService.sync_live_workbook_to_disk()
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="FinTrack_Live_Database.xlsx"',
                "Cache-Control": "no-store",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel workbook: {e}",
        )


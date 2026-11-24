"""
FinTrack - Financial Transfers & Transactions API Endpoints
File: api/routes/transfers.py
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.deps import get_current_user, require_customer
from api.schemas import (
    RecipientLookupResponse,
    TransactionOut,
    TransferRequest,
    TransferResponse,
)
from database_layer.postgres import (
    AccountFrozenError,
    ConcurrencyError,
    DatabaseError,
    InsufficientFundsError,
    NotFoundError,
    fetch_all,
    fetch_one,
)
from services.auth_service import AuthUser
from services.transfer_service import TransferService

router = APIRouter(prefix="/api/transfers", tags=["Transfers"])


@router.post("", response_model=TransferResponse)
def execute_transfer(
    req: TransferRequest,
    request: Request,
    user: AuthUser = Depends(require_customer),
):
    """
    Execute an atomic transfer between two accounts.
    - Ascending deterministic row locks prevent deadlocks.
    - Idempotency key deduplication.
    - Transfers >= INR 10,000 are held as FLAGGED with zero money movement.
    - Double-entry ledger entries (1 Debit, 1 Credit).
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Unknown Client")

    try:
        result = TransferService.execute_transfer(
            authenticated_customer_id=user.customer_id,
            sender_account_id=req.sender_account_id,
            receiver_account_id=req.receiver_account_id,
            amount=req.amount,
            description=req.description,
            idempotency_key=req.idempotency_key,
            ip_address=client_ip,
            device_info=user_agent,
        )
        return TransferResponse(
            status=result["status"],
            transaction_id=result.get("transaction_id"),
            alert_id=result.get("alert_id"),
            amount=result["amount"],
            is_replay=result.get("is_replay", False),
            message=result["message"],
        )
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AccountFrozenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (ValueError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("", response_model=List[TransactionOut])
def get_transactions(
    account_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
):
    """
    List transactions with optional filtering and pagination.
    Customers only view transactions relating to their own accounts.
    """
    params: List[Any] = []
    where_clauses: List[str] = []

    if user.is_customer():
        where_clauses.append("""
            (t.sender_account_id IN (SELECT account_id FROM accounts WHERE customer_id = %s)
             OR t.receiver_account_id IN (SELECT account_id FROM accounts WHERE customer_id = %s))
        """)
        params.extend([user.customer_id, user.customer_id])

    if account_id:
        where_clauses.append("(t.sender_account_id = %s OR t.receiver_account_id = %s)")
        params.extend([account_id, account_id])

    if status_filter:
        where_clauses.append("t.status = %s")
        params.append(status_filter.upper())

    if search:
        where_clauses.append("(t.description ILIKE %s OR sc.full_name ILIKE %s OR rc.full_name ILIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

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
    rows = fetch_all(query, tuple(params))

    # Add direction helper if requested by customer
    if user.is_customer():
        user_accounts = {
            acc["account_id"]
            for acc in fetch_all("SELECT account_id FROM accounts WHERE customer_id = %s;", (user.customer_id,))
        }
        for r in rows:
            r["direction"] = "DEBIT" if r["sender_account_id"] in user_accounts else "CREDIT"

    return rows


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction_by_id(transaction_id: int, user: AuthUser = Depends(get_current_user)):
    """Fetch details of a single transaction with authorization check."""
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
            t.transaction_date
        FROM transactions t
        JOIN accounts sa ON t.sender_account_id = sa.account_id
        JOIN customers sc ON sa.customer_id = sc.customer_id
        JOIN accounts ra ON t.receiver_account_id = ra.account_id
        JOIN customers rc ON ra.customer_id = rc.customer_id
        WHERE t.transaction_id = %s;
    """
    tx = fetch_one(query, (transaction_id,))
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

    if user.is_customer():
        user_accounts = {
            acc["account_id"]
            for acc in fetch_all("SELECT account_id FROM accounts WHERE customer_id = %s;", (user.customer_id,))
        }
        if tx["sender_account_id"] not in user_accounts and tx["receiver_account_id"] not in user_accounts:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")
        tx["direction"] = "DEBIT" if tx["sender_account_id"] in user_accounts else "CREDIT"

    return tx


@router.get("/recipient/{account_number}", response_model=RecipientLookupResponse)
def lookup_recipient(account_number: int, user: AuthUser = Depends(get_current_user)):
    """Verify recipient account before submitting transfer."""
    query = """
        SELECT a.account_id, c.full_name AS customer_name, a.account_type, a.is_frozen
        FROM accounts a
        JOIN customers c ON a.customer_id = c.customer_id
        WHERE a.account_id = %s;
    """
    row = fetch_one(query, (account_number,))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account #{account_number} does not exist.")
    return row


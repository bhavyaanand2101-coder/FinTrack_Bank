"""
FinTrack - Smart Digital Banking & Loan Management System
PostgreSQL Query Execution, Helper Utilities & Standardized Exceptions
File: database_layer/postgres.py
"""

from collections.abc import Sequence
from contextlib import contextmanager
from decimal import Decimal
import logging
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
import psycopg2
from psycopg2 import errorcodes
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import connection as PgConnection

from database_layer.db import get_db_connection

logger = logging.getLogger(__name__)


# ============================================================================
# Standardized Database Exceptions
# ============================================================================

class DatabaseError(Exception):
    """Base exception for all database-related operations."""
    pass


class NotFoundError(DatabaseError):
    """Raised when an expected record is not found."""
    pass


class ConcurrencyError(DatabaseError):
    """Raised during deadlocks or serialization failures."""
    pass


class IntegrityError(DatabaseError):
    """Raised when database constraints (FK, CHECK, UNIQUE) are violated."""
    pass


class InsufficientFundsError(DatabaseError):
    """Raised when account balance is less than requested debit."""
    pass


class AccountFrozenError(DatabaseError):
    """Raised when operating on a frozen account."""
    pass


class DuplicateIdempotencyError(DatabaseError):
    """Raised when a transfer request with existing idempotency key is submitted."""
    def __init__(self, message: str, transaction_record: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.transaction_record = transaction_record


def set_rls_context(conn: PgConnection, customer_id: Optional[int] = None, role: Optional[str] = "CUSTOMER") -> None:
    """
    Set PostgreSQL Row Level Security (RLS) session variables.
    Enforces engine-level isolation: queries executed under this connection
    cannot read or modify accounts or transactions belonging to another customer.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_customer_id', %s, false);", (str(customer_id) if customer_id else "",))
        cur.execute("SELECT set_config('app.current_user_role', %s, false);", (str(role) if role else "CUSTOMER",))


# ============================================================================
# Transaction Context Manager
# ============================================================================

@contextmanager
def transaction(existing_conn: Optional[PgConnection] = None) -> Generator[PgConnection, None, None]:
    """
    Context manager managing a dedicated, explicit database transaction.
    
    If existing_conn is provided, it uses it without nesting commits/rollbacks.
    Otherwise, it checks out a connection from the pool, commits upon normal exit,
    and rolls back upon exception.
    """
    if existing_conn is not None:
        # Existing transaction boundary managed by outer caller
        yield existing_conn
    else:
        with get_db_connection() as conn:
            try:
                yield conn
                conn.commit()
            except psycopg2.Error as pg_err:
                conn.rollback()
                _handle_pg_error(pg_err)
            except Exception:
                conn.rollback()
                raise


def _handle_pg_error(pg_err: psycopg2.Error) -> None:
    """Translate low-level psycopg2 error codes into standardized exceptions."""
    err_code = getattr(pg_err, "pgcode", "")
    err_msg = str(pg_err).strip()

    if err_code == errorcodes.DEADLOCK_DETECTED or err_code == errorcodes.SERIALIZATION_FAILURE:
        raise ConcurrencyError(f"Database concurrency conflict detected: {err_msg}") from pg_err

    if err_code == errorcodes.UNIQUE_VIOLATION:
        raise IntegrityError(f"Unique constraint violation: {err_msg}") from pg_err

    if err_code == errorcodes.CHECK_VIOLATION:
        if "chk_positive_balance" in err_msg or "balance" in err_msg:
            raise InsufficientFundsError("Insufficient funds: balance cannot become negative.") from pg_err
        raise IntegrityError(f"Check constraint violation: {err_msg}") from pg_err

    if err_code == errorcodes.FOREIGN_KEY_VIOLATION:
        raise IntegrityError(f"Foreign key constraint violation: {err_msg}") from pg_err

    raise DatabaseError(f"PostgreSQL database error [{err_code}]: {err_msg}") from pg_err


# ============================================================================
# Safe Query Execution Helpers (Parameterized Only)
# ============================================================================

def fetch_one(
    query: str,
    params: Optional[Union[Sequence[Any], Dict[str, Any], Tuple[Any, ...]]] = None,
    conn: Optional[PgConnection] = None,
) -> Optional[Dict[str, Any]]:
    """
    Execute a parameterized SELECT query and return the first row as a dictionary.
    """
    def _run(active_conn: PgConnection) -> Optional[Dict[str, Any]]:
        with active_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row is not None else None

    if conn is not None:
        return _run(conn)
    with get_db_connection() as active_conn:
        return _run(active_conn)


def fetch_all(
    query: str,
    params: Optional[Union[Sequence[Any], Dict[str, Any], Tuple[Any, ...]]] = None,
    conn: Optional[PgConnection] = None,
) -> List[Dict[str, Any]]:
    """
    Execute a parameterized SELECT query and return all matching rows as dictionaries.
    """
    def _run(active_conn: PgConnection) -> List[Dict[str, Any]]:
        with active_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    if conn is not None:
        return _run(conn)
    with get_db_connection() as active_conn:
        return _run(active_conn)


def execute_scalar(
    query: str,
    params: Optional[Union[Sequence[Any], Dict[str, Any], Tuple[Any, ...]]] = None,
    conn: Optional[PgConnection] = None,
) -> Any:
    """
    Execute a query returning a single scalar value (e.g. COUNT, SUM, RETURNING id).
    """
    def _run(active_conn: PgConnection) -> Any:
        with active_conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return row[0] if row is not None else None

    if conn is not None:
        return _run(conn)
    with get_db_connection() as active_conn:
        return _run(active_conn)


def execute_update(
    query: str,
    params: Optional[Union[Sequence[Any], Dict[str, Any], Tuple[Any, ...]]] = None,
    conn: Optional[PgConnection] = None,
) -> int:
    """
    Execute an INSERT, UPDATE, or DELETE query and return the affected row count.
    """
    def _run(active_conn: PgConnection) -> int:
        with active_conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount

    if conn is not None:
        return _run(conn)
    with transaction() as active_conn:
        return _run(active_conn)

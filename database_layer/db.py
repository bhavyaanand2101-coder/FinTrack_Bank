"""
FinTrack - Smart Digital Banking & Loan Management System
Database Connection Pooling Module
File: database_layer/db.py
"""

from contextlib import contextmanager
import logging
import threading
import time
from typing import Generator, Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extensions import connection as PgConnection, STATUS_IN_TRANSACTION

from config.settings import settings

logger = logging.getLogger(__name__)

# Global non-streamlit pool fallback (for pytest, standalone worker, migrations)
_GLOBAL_POOL: Optional[pool.ThreadedConnectionPool] = None
_POOL_LOCK = threading.Lock()


def _create_raw_pool() -> pool.ThreadedConnectionPool:
    """Instantiate a new psycopg2 ThreadedConnectionPool with timeout options."""
    # Ensure statement timeout and connection parameters
    connect_args = {
        "options": f"-c statement_timeout={settings.DB_TIMEOUT_SECONDS * 1000}",
        "connect_timeout": settings.DB_TIMEOUT_SECONDS,
    }

    raw_pool = pool.ThreadedConnectionPool(
        minconn=settings.DB_POOL_MIN,
        maxconn=settings.DB_POOL_MAX,
        dsn=settings.POSTGRES_URI,
        **connect_args,
    )
    logger.info(
        "Initialized PostgreSQL ThreadedConnectionPool (min=%d, max=%d)",
        settings.DB_POOL_MIN,
        settings.DB_POOL_MAX,
    )
    return raw_pool


def get_connection_pool() -> pool.ThreadedConnectionPool:
    """
    Get or initialize the thread-safe connection pool using a singleton lock.
    """
    global _GLOBAL_POOL
    with _POOL_LOCK:
        if _GLOBAL_POOL is None or _GLOBAL_POOL.closed:
            _GLOBAL_POOL = _create_raw_pool()
        return _GLOBAL_POOL


def close_connection_pool() -> None:
    """Gracefully close all connections in the global pool."""
    global _GLOBAL_POOL
    with _POOL_LOCK:
        if _GLOBAL_POOL is not None and not _GLOBAL_POOL.closed:
            _GLOBAL_POOL.closeall()
            _GLOBAL_POOL = None
            logger.info("Closed all PostgreSQL connection pool instances.")


def check_postgres_health() -> bool:
    """Verify pool connectivity by executing a lightweight query."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                res = cur.fetchone()
                return bool(res and res[0] == 1)
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: %s", exc)
        return False


@contextmanager
def get_db_connection() -> Generator[PgConnection, None, None]:
    """
    Context manager to safely acquire and return a connection from the pool.
    
    Guarantees:
    - Never shares connections across threads/sessions.
    - Tests connection validity.
    - Automatically rolls back any dangling uncommitted transactions on exception or exit.
    - Safely returns healthy connections to the pool in finally block.
    - Discards corrupted connections.
    """
    pool_instance = get_connection_pool()
    conn: Optional[PgConnection] = None
    max_retries = 3
    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            conn = pool_instance.getconn()
            break
        except pool.PoolError as pe:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))
                continue
            raise RuntimeError(
                f"PostgreSQL Connection Pool exhausted after {max_retries} attempts: {pe}"
            ) from pe

    assert conn is not None, "Failed to obtain database connection from pool."

    # Validate that connection is active and not closed
    if conn.closed:
        try:
            pool_instance.putconn(conn, close=True)
        except Exception:
            pass
        conn = pool_instance.getconn()

    try:
        yield conn
    except Exception:
        # Roll back on error before returning
        if not conn.closed:
            try:
                conn.rollback()
            except Exception as rb_err:
                logger.warning("Failed to rollback connection on error: %s", rb_err)
        raise
    finally:
        # Guarantee return to pool in finally
        if conn is not None and not conn.closed:
            try:
                # If transaction is still open (uncommitted/unhandled), roll it back cleanly
                if conn.status == STATUS_IN_TRANSACTION:
                    conn.rollback()
                pool_instance.putconn(conn)
            except Exception as put_err:
                logger.error("Error returning connection to pool: %s", put_err)
                try:
                    pool_instance.putconn(conn, close=True)
                except Exception:
                    pass
        elif conn is not None and conn.closed:
            try:
                pool_instance.putconn(conn, close=True)
            except Exception:
                pass

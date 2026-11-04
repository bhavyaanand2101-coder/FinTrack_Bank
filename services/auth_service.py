"""
FinTrack - Smart Digital Banking & Loan Management System
Authentication & Authorization Service
File: services/auth_service.py
"""

from collections import defaultdict
from dataclasses import dataclass
import datetime
from decimal import Decimal
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from config.settings import settings
from database_layer.postgres import DatabaseError, fetch_one, transaction
from security import security_validator
from services.audit_service import audit_service

logger = logging.getLogger(__name__)

# Argon2id password hasher instance
ph = PasswordHasher()

# Login attempt throttling: tracks failed attempts per username and IP
_FAILED_ATTEMPTS: Dict[str, list[float]] = defaultdict(list)
_THROTTLE_LOCK = threading.Lock()
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes


@dataclass
class AuthUser:
    """Session representation of an authenticated user."""
    user_id: int
    customer_id: Optional[int]
    username: str
    role: str  # 'CUSTOMER' or 'ADMIN'
    is_active: bool
    full_name: Optional[str] = None
    email: Optional[str] = None
    login_time: Optional[float] = None

    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    def is_customer(self) -> bool:
        return self.role == "CUSTOMER"

    def is_session_expired(self) -> bool:
        if not self.login_time:
            return True
        timeout_seconds = settings.SESSION_TIMEOUT_MINUTES * 60
        return (time.time() - self.login_time) > timeout_seconds


class AuthService:
    """Manages secure registration, credential verification, throttling, and session tokens."""

    @staticmethod
    def hash_password(plain_password: str) -> str:
        """Hash a plaintext password with Argon2id."""
        if not plain_password or len(plain_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return ph.hash(plain_password)

    @staticmethod
    def verify_password(password_hash: str, plain_password: str) -> bool:
        """Verify plaintext password against stored Argon2id hash."""
        try:
            return ph.verify(password_hash, plain_password)
        except (VerifyMismatchError, VerificationError):
            return False

    @staticmethod
    def check_throttle(identifier: str) -> Tuple[bool, int]:
        """
        Check if an account or IP is temporarily throttled due to brute-force attempts.
        Returns: (is_throttled, seconds_remaining)
        """
        now = time.time()
        with _THROTTLE_LOCK:
            timestamps = [t for t in _FAILED_ATTEMPTS[identifier] if now - t < LOCKOUT_WINDOW_SECONDS]
            _FAILED_ATTEMPTS[identifier] = timestamps
            if len(timestamps) >= MAX_FAILED_ATTEMPTS:
                remaining = int(LOCKOUT_WINDOW_SECONDS - (now - timestamps[0]))
                return True, max(1, remaining)
            return False, 0

    @staticmethod
    def record_failed_attempt(identifier: str) -> None:
        """Record a failed login attempt for throttling."""
        with _THROTTLE_LOCK:
            _FAILED_ATTEMPTS[identifier].append(time.time())

    @staticmethod
    def clear_failed_attempts(identifier: str) -> None:
        """Reset failed attempts upon successful login."""
        with _THROTTLE_LOCK:
            _FAILED_ATTEMPTS.pop(identifier, None)

    @classmethod
    def login(
        cls,
        username: str,
        plain_password: str,
        ip_address: str = "127.0.0.1",
        device_info: str = "Desktop Client",
    ) -> AuthUser:
        """
        Authenticate a user securely with throttling and audit tracking.
        """
        clean_user = username.strip().lower()

        # Check throttling
        is_locked, remaining_sec = cls.check_throttle(clean_user)
        if is_locked:
            audit_service.record_outbox_event(
                "LOGIN_LOCKED",
                {
                    "username": clean_user,
                    "ip_address": ip_address,
                    "reason": f"Account temporarily locked for {remaining_sec}s.",
                },
            )
            raise DatabaseError(
                f"Too many failed login attempts. Please wait {remaining_sec} seconds before retrying."
            )

        query = """
            SELECT 
                u.user_id, u.customer_id, u.username, u.password_hash, u.role, u.is_active,
                c.full_name, c.email
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.customer_id
            WHERE LOWER(u.username) = %s;
        """
        user_row = fetch_one(query, (clean_user,))

        # Constant-time mitigation against user enumeration
        dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummySaltString12345$dummyHashValueString12345678901234567890"

        if user_row is None:
            cls.verify_password(dummy_hash, plain_password)
            cls.record_failed_attempt(clean_user)
            audit_service.record_outbox_event(
                "LOGIN_FAILED",
                {"username": clean_user, "ip_address": ip_address, "reason": "User not found."},
            )
            raise DatabaseError("Invalid username or password.")

        if not user_row["is_active"]:
            audit_service.record_outbox_event(
                "LOGIN_REJECTED",
                {"username": clean_user, "ip_address": ip_address, "reason": "User account inactive."},
            )
            raise DatabaseError("Your account has been deactivated. Please contact bank administration.")

        if not cls.verify_password(user_row["password_hash"], plain_password):
            cls.record_failed_attempt(clean_user)
            audit_service.record_outbox_event(
                "LOGIN_FAILED",
                {"username": clean_user, "ip_address": ip_address, "reason": "Password mismatch."},
            )
            raise DatabaseError("Invalid username or password.")

        # Success: clear throttling
        cls.clear_failed_attempts(clean_user)

        auth_user = AuthUser(
            user_id=user_row["user_id"],
            customer_id=user_row["customer_id"],
            username=user_row["username"],
            role=user_row["role"],
            is_active=user_row["is_active"],
            full_name=user_row.get("full_name"),
            email=user_row.get("email"),
            login_time=time.time(),
        )

        audit_service.record_outbox_event(
            "LOGIN_SUCCESS",
            {
                "user_id": auth_user.user_id,
                "customer_id": auth_user.customer_id,
                "username": auth_user.username,
                "role": auth_user.role,
                "ip_address": ip_address,
                "device_info": device_info,
            },
        )

        return auth_user

    @classmethod
    def register_customer(
        cls,
        full_name: str,
        email: str,
        phone: str,
        username: str,
        plain_password: str,
        initial_deposit: Decimal = Decimal("1000.00"),
        ip_address: str = "127.0.0.1",
    ) -> Tuple[int, int, int]:
        """
        Atomically register a new customer, user record, and primary SAVINGS account.

        Returns:
            Tuple of (customer_id, user_id, account_id)
        """
        clean_name = security_validator.sanitize_text(full_name, max_len=100)
        clean_email = security_validator.validate_email(email)
        clean_phone = security_validator.sanitize_text(phone, max_len=20)
        clean_username = security_validator.validate_username(username)

        if not clean_name:
            raise ValueError("Full name is required.")
        if "@" not in clean_email or "." not in clean_email:
            raise ValueError("Valid email address is required.")
        if len(clean_phone) < 8:
            raise ValueError("Valid phone number is required.")
        if len(clean_username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if initial_deposit < Decimal("0.00"):
            raise ValueError("Initial deposit cannot be negative.")

        password_hash = cls.hash_password(plain_password)

        with transaction() as conn:
            # 1. Insert customer
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO customers (full_name, email, phone)
                    VALUES (%s, %s, %s)
                    RETURNING customer_id;
                    """,
                    (clean_name, clean_email, clean_phone),
                )
                customer_id = cur.fetchone()[0]

                # 2. Insert user
                cur.execute(
                    """
                    INSERT INTO users (customer_id, username, password_hash, role, is_active)
                    VALUES (%s, %s, %s, 'CUSTOMER', TRUE)
                    RETURNING user_id;
                    """,
                    (customer_id, clean_username, password_hash),
                )
                user_id = cur.fetchone()[0]

                # 3. Create default primary SAVINGS account
                cur.execute(
                    """
                    INSERT INTO accounts (customer_id, account_type, balance, currency, is_frozen)
                    VALUES (%s, 'SAVINGS', %s, 'INR', FALSE)
                    RETURNING account_id;
                    """,
                    (customer_id, initial_deposit),
                )
                account_id = cur.fetchone()[0]

            # 4. Outbox audit event
            audit_service.record_outbox_event(
                "CUSTOMER_REGISTERED",
                {
                    "customer_id": customer_id,
                    "user_id": user_id,
                    "username": clean_username,
                    "primary_account_id": account_id,
                    "initial_deposit": float(initial_deposit),
                    "ip_address": ip_address,
                },
                conn=conn,
            )

        logger.info("Successfully registered customer %d, user %d, account %d", customer_id, user_id, account_id)
        return customer_id, user_id, account_id


auth_service = AuthService()


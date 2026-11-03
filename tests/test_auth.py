"""
FinTrack - Authentication and Authorization Unit Tests
File: tests/test_auth.py
"""

from decimal import Decimal
import time
import pytest
from argon2 import PasswordHasher

from database_layer.postgres import DatabaseError, execute_update
from services.auth_service import AuthService, AuthUser, auth_service


def test_password_hash_and_verification():
    raw_pass = "SecurePass2026!"
    hashed = auth_service.hash_password(raw_pass)
    assert hashed.startswith("$argon2id$")
    assert auth_service.verify_password(hashed, raw_pass) is True
    assert auth_service.verify_password(hashed, "WrongPass123") is False


def test_valid_customer_login():
    user = auth_service.login("arun_kumar", "Customer123!")
    assert isinstance(user, AuthUser)
    assert user.username == "arun_kumar"
    assert user.role == "CUSTOMER"
    assert user.is_customer() is True
    assert user.is_admin() is False
    assert user.customer_id == 1


def test_valid_admin_login():
    user = auth_service.login("admin", "AdminPassword123!")
    assert isinstance(user, AuthUser)
    assert user.username == "admin"
    assert user.role == "ADMIN"
    assert user.is_admin() is True
    assert user.is_customer() is False


def test_invalid_password_login():
    with pytest.raises(DatabaseError, match="Invalid username or password"):
        auth_service.login("arun_kumar", "IncorrectPassword!")


def test_nonexistent_user_login():
    with pytest.raises(DatabaseError, match="Invalid username or password"):
        auth_service.login("non_existent_user_999", "SomePassword123!")


def test_inactive_user_rejection():
    # Temporarily deactivate a user
    execute_update("UPDATE users SET is_active = FALSE WHERE username = 'rohit_verma';")
    try:
        with pytest.raises(DatabaseError, match="account has been deactivated"):
            auth_service.login("rohit_verma", "Customer123!")
    finally:
        execute_update("UPDATE users SET is_active = TRUE WHERE username = 'rohit_verma';")


def test_session_expiration():
    user = AuthUser(
        user_id=10,
        customer_id=1,
        username="test_session_user",
        role="CUSTOMER",
        is_active=True,
        login_time=time.time() - 3600,  # 1 hour ago (timeout is 30 mins)
    )
    assert user.is_session_expired() is True

    fresh_user = AuthUser(
        user_id=10,
        customer_id=1,
        username="fresh_user",
        role="CUSTOMER",
        is_active=True,
        login_time=time.time(),
    )
    assert fresh_user.is_session_expired() is False


def test_customer_registration():
    unique_user = f"new_user_{int(time.time())}"
    c_id, u_id, a_id = auth_service.register_customer(
        full_name="Test Registrant",
        email=f"{unique_user}@example.com",
        phone=f"+9199{int(time.time()) % 100000000:08d}",
        username=unique_user,
        plain_password="RegisterPass123!",
        initial_deposit=Decimal("2500.00"),
    )
    assert c_id > 0
    assert u_id > 0
    assert a_id > 0

    # Verify newly registered user can log in immediately
    logged_in = auth_service.login(unique_user, "RegisterPass123!")
    assert logged_in.customer_id == c_id


def test_login_throttling():
    test_user = f"throttle_target_{int(time.time())}"
    # Generate 5 failed attempts
    for _ in range(5):
        try:
            auth_service.login(test_user, "WrongPassword!")
        except Exception:
            pass

    # 6th attempt should trigger rate limiting / lockout
    with pytest.raises(DatabaseError, match="Too many failed login attempts"):
        auth_service.login(test_user, "WrongPassword!")

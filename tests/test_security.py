"""
FinTrack - Security Hardening, Input Sanitization & Threat Protection Tests
File: tests/test_security.py
"""

from decimal import Decimal
import time
import pytest

from database_layer.postgres import DatabaseError
from security import security_validator
from services.account_service import account_service
from services.transfer_service import transfer_service


def test_input_sanitization_xss_prevention():
    malicious_input = "<script>alert('XSS')</script>Normal Text"
    sanitized = security_validator.sanitize_text(malicious_input)
    assert "<script>" not in sanitized
    assert "&lt;script&gt;" in sanitized or "script" in sanitized
    assert "Normal Text" in sanitized

    # Test stripping null bytes and ASCII control characters
    control_chars = "Hello\x00\x08World\x1F!"
    clean_ctrl = security_validator.sanitize_text(control_chars)
    assert clean_ctrl == "HelloWorld!"


def test_username_validation():
    assert security_validator.validate_username("valid_user_123") == "valid_user_123"

    with pytest.raises(ValueError, match="between 3 and 30 characters"):
        security_validator.validate_username("ab")

    with pytest.raises(ValueError, match="only letters, numbers, and underscores"):
        security_validator.validate_username("user;DROP TABLE users;--")

    with pytest.raises(ValueError, match="only letters, numbers, and underscores"):
        security_validator.validate_username("<script>alert(1)</script>")


def test_email_validation():
    assert security_validator.validate_email("user@example.com") == "user@example.com"

    with pytest.raises(ValueError, match="Invalid email address"):
        security_validator.validate_email("invalid-email-address")

    with pytest.raises(ValueError, match="Invalid email address"):
        security_validator.validate_email("user@.com")


def test_sliding_window_rate_limiting():
    key = f"rate_limit_test_{int(time.time() * 1000)}"

    # Allow up to 3 requests in 10 seconds
    for _ in range(3):
        allowed, _ = security_validator.check_rate_limit(key, max_requests=3, window_seconds=10)
        assert allowed is True

    # 4th request must be rate-limited
    allowed, retry_after = security_validator.check_rate_limit(key, max_requests=3, window_seconds=10)
    assert allowed is False
    assert retry_after > 0


def test_file_upload_type_and_magic_byte_validation():
    # Valid PDF with correct magic header
    valid_pdf = b"%PDF-1.4 sample content"
    assert security_validator.validate_file_upload(valid_pdf, "statement.pdf") is True

    # File with .pdf extension but fake / invalid header
    fake_pdf = b"NOT_A_REAL_PDF"
    with pytest.raises(ValueError, match="Corrupted or invalid PDF file header"):
        security_validator.validate_file_upload(fake_pdf, "malicious.pdf")

    # Disallowed executable extension
    dangerous_file = b"MZ\x90\x00executable content"
    with pytest.raises(ValueError, match="File extension not permitted"):
        security_validator.validate_file_upload(dangerous_file, "exploit.exe")

    # File exceeding size limit
    oversized = b"A" * (6 * 1024 * 1024)  # 6MB
    with pytest.raises(ValueError, match="exceeds limit"):
        security_validator.validate_file_upload(oversized, "large.png", max_size_mb=5)


def test_idor_protection_account_access():
    """
    IDOR (Insecure Direct Object Reference) Test:
    Customer 1 must not be allowed to read or access Customer 2's account details.
    """
    # Customer 1 attempts to query account 1003 (owned by Customer 2)
    with pytest.raises(DatabaseError, match="Unauthorized: You do not own"):
        account_service.get_account_by_id(account_id=1003, customer_id=1)


def test_idor_protection_transfer_source():
    """
    IDOR Test:
    Customer 1 must not be allowed to initiate a transfer debited from Customer 2's account.
    """
    with pytest.raises(DatabaseError, match="Unauthorized: You do not own sender account"):
        transfer_service.execute_transfer(
            authenticated_customer_id=1,
            sender_account_id=1003,  # Owned by Customer 2
            receiver_account_id=1001,
            amount=Decimal("100.00"),
        )

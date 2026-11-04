"""
FinTrack - Smart Digital Banking & Loan Management System
Application Security, Input Sanitization & Rate Limiting Module
File: security.py
"""

from collections import defaultdict
from decimal import Decimal
import html
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Thread-safe in-memory sliding window rate limiter
_RATE_LIMITS: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT_LOCK = threading.Lock()


class SecurityValidator:
    """Enterprise Application Security and Input Validation Helpers."""

    @staticmethod
    def sanitize_text(text: Optional[str], max_len: int = 500) -> str:
        """
        Sanitize string inputs to prevent Stored XSS and SQL injection formatting.
        - Trims whitespace.
        - Escapes HTML entities (&, <, >, ", ').
        - Strips ASCII control characters.
        """
        if not text:
            return ""
        # Remove null bytes and control chars
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(text).strip())
        # Escape HTML
        escaped = html.escape(cleaned, quote=True)
        return escaped[:max_len]

    @staticmethod
    def validate_username(username: str) -> str:
        """Enforce strict alphanumeric and underscore rules for usernames."""
        clean = username.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", clean):
            raise ValueError(
                "Username must be between 3 and 30 characters and contain only letters, numbers, and underscores."
            )
        return clean

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format according to RFC 5322 subset."""
        clean = email.strip().lower()
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, clean) or len(clean) > 254:
            raise ValueError("Invalid email address format.")
        return clean

    @staticmethod
    def validate_amount(
        amount: Union[Decimal, float, int, str],
        min_val: Decimal = Decimal("1.00"),
        max_val: Decimal = Decimal("10000000.00"),
    ) -> Decimal:
        """Ensure monetary values are valid, positive Decimals within business thresholds."""
        try:
            val = Decimal(str(amount)).quantize(Decimal("0.01"))
        except Exception as e:
            raise ValueError(f"Invalid monetary amount format: {amount}") from e

        if val < min_val:
            raise ValueError(f"Amount must be at least ₹{min_val:,.2f}.")
        if val > max_val:
            raise ValueError(f"Amount exceeds maximum allowed limit of ₹{max_val:,.2f}.")
        return val

    @staticmethod
    def check_rate_limit(
        identifier: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> Tuple[bool, int]:
        """
        Sliding-window rate limiter for sensitive operations (transfers, logins, applications).
        Returns: (is_allowed, retry_after_seconds)
        """
        now = time.time()
        with _RATE_LIMIT_LOCK:
            timestamps = [t for t in _RATE_LIMITS[identifier] if now - t < window_seconds]
            _RATE_LIMITS[identifier] = timestamps
            if len(timestamps) >= max_requests:
                oldest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                return False, retry_after

            _RATE_LIMITS[identifier].append(now)
            return True, 0

    @staticmethod
    def validate_file_upload(
        file_bytes: bytes,
        filename: str,
        max_size_mb: int = 5,
        allowed_extensions: Optional[List[str]] = None,
    ) -> bool:
        """
        Validate file uploads to prevent arbitrary code execution and MIME confusion.
        """
        if allowed_extensions is None:
            allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg"]

        # Check extension
        lower_name = filename.lower()
        if not any(lower_name.endswith(ext) for ext in allowed_extensions):
            raise ValueError(f"File extension not permitted. Allowed: {', '.join(allowed_extensions)}")

        # Check size
        size_mb = len(file_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise ValueError(f"File size ({size_mb:.2f}MB) exceeds limit of {max_size_mb}MB.")

        # Check magic bytes
        # PDF magic: %PDF-
        if lower_name.endswith(".pdf") and not file_bytes.startswith(b"%PDF-"):
            raise ValueError("Corrupted or invalid PDF file header.")
        # PNG magic: \x89PNG\r\n\x1a\n
        if lower_name.endswith(".png") and not file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Corrupted or invalid PNG image header.")
        # JPEG magic: \xff\xd8\xff
        if lower_name.endswith((".jpg", ".jpeg")) and not file_bytes.startswith(b"\xff\xd8\xff"):
            raise ValueError("Corrupted or invalid JPEG image header.")

        return True


security_validator = SecurityValidator()

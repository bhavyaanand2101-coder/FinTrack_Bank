"""
FinTrack - Smart Digital Banking & Loan Management System
Application Security, Input Sanitization, Rate Limiting & Webhook Security Module
File: security.py
"""

from collections import defaultdict
from decimal import Decimal
import hashlib
import hmac
import html
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Thread-safe in-memory sliding window rate limiter
_RATE_LIMITS: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT_LOCK = threading.Lock()


class SecurityValidator:
    """Enterprise Application Security, Input Validation & Cryptographic Verification Helpers."""

    @staticmethod
    def sanitize_text(text: Optional[str], max_len: int = 500) -> str:
        """
        Sanitize string inputs to prevent Stored XSS and SQL injection formatting.
        - Trims whitespace.
        - Escapes HTML entities (&, <, >, ", ').
        - Strips ASCII control characters and null bytes.
        """
        if not text:
            return ""
        # Remove null bytes and control chars
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(text).strip())
        # Escape HTML
        escaped = html.escape(cleaned, quote=True)
        return escaped[:max_len]

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize uploaded filenames to eliminate Path Traversal attacks (../, absolute paths, null bytes).
        Returns a clean base filename.
        """
        if not filename:
            return "uploaded_file"
        # Normalize Windows path separators
        normalized = filename.replace("\\", "/")
        # Extract base name to strip path components
        base = os.path.basename(normalized)
        # Strip directory traversal symbols and non-whitelisted characters
        clean = re.sub(r"[^\w\-.]", "_", base).strip("._")
        return clean if clean else "uploaded_file"

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
        Validate file uploads to prevent arbitrary code execution, MIME confusion, and path traversal.
        Validates size, extension, and deep magic byte signatures.
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

    @staticmethod
    def generate_webhook_signature(
        payload: Union[bytes, str],
        secret: str,
        timestamp: Optional[int] = None,
    ) -> str:
        """
        Generate a cryptographically secure HMAC-SHA256 signature for outbound/inbound webhooks.
        Format: t={timestamp},v1={hex_signature}
        """
        ts = int(timestamp or time.time())
        raw_bytes = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        signed_payload = f"{ts}.".encode("utf-8") + raw_bytes
        signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        return f"t={ts},v1={signature}"

    @staticmethod
    def verify_webhook_signature(
        payload: Union[bytes, str],
        signature_header: str,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Verify incoming webhook signature using HMAC-SHA256, constant-time comparison,
        and timestamp replay attack mitigation.
        """
        if not signature_header or not secret:
            return False

        # Parse header: t=1614555000,v1=abcdef...
        elements = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
        ts_str = elements.get("t")
        v1_sig = elements.get("v1")

        if not ts_str or not v1_sig:
            return False

        try:
            ts = int(ts_str)
        except ValueError:
            return False

        # Check timestamp replay tolerance
        now = int(time.time())
        if abs(now - ts) > tolerance_seconds:
            return False

        # Re-compute expected signature
        raw_bytes = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        signed_payload = f"{ts}.".encode("utf-8") + raw_bytes
        expected_sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

        # Timing-safe constant time comparison to mitigate timing attacks
        return hmac.compare_digest(expected_sig, v1_sig)

    @staticmethod
    def assert_no_command_execution(text: str) -> None:
        """
        Verify that user-supplied input does not contain command injection delimiters
        or shell evaluation tokens.
        """
        if not text:
            return
        # Reject shell operators, process substitution, or evaluation strings
        dangerous_patterns = [
            r"[`]",           # Backticks
            r"\$\(.*\)",      # $(command)
            r"[;&|><]",       # Command delimiters and redirects
            r"\x00",          # Null byte
            r"(?i)\bexec\b",  # exec token
            r"(?i)\beval\b",  # eval token
            r"(?i)\bsystem\b" # system call
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, text):
                raise ValueError(f"Dangerous input token detected. Shell/command execution is strictly prohibited.")


security_validator = SecurityValidator()

"""
FinTrack - Smart Digital Banking & Loan Management System
Private Secure File Storage Service
File: services/storage_service.py
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import uuid

from config.settings import BASE_DIR
from database_layer.postgres import DatabaseError, NotFoundError
from security import security_validator

logger = logging.getLogger(__name__)

# Private storage directory - strictly isolated from web root
STORAGE_DIR = Path(BASE_DIR) / "storage" / "private"


class PrivateStorageService:
    """
    Enterprise Secure Storage Engine.
    Guarantees:
    - Files are stored outside web-accessible roots with restrictive POSIX permissions (0600).
    - Randomized non-sequential UUID keys prevent enumeration and IDOR.
    - Deep magic-byte and MIME verification prior to persisting.
    - Path traversal strictly blocked via root boundary enforcement.
    - Authenticated access control: only file owner or administrators can retrieve documents.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or STORAGE_DIR
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Create private storage directory if not exists with restricted permissions."""
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, mode=0o700, exist_ok=True)

    def store_file(
        self,
        file_bytes: bytes,
        original_filename: str,
        owner_customer_id: int,
        category: str = "loan_document",
    ) -> Dict[str, Any]:
        """
        Validate and store a file into private secure storage.
        """
        # 1. Sanitize filename and validate contents/magic bytes
        clean_filename = security_validator.sanitize_filename(original_filename)
        security_validator.validate_file_upload(file_bytes, clean_filename)

        # 2. Generate secure non-guessable storage identifier
        file_uuid = str(uuid.uuid4())
        ext = os.path.splitext(clean_filename)[1].lower()
        stored_filename = f"{file_uuid}{ext}"

        target_path = (self.storage_dir / stored_filename).resolve()

        # 3. Path Traversal Guard: Ensure target path remains within storage_dir
        if not str(target_path).startswith(str(self.storage_dir.resolve())):
            raise DatabaseError("Security violation: Path traversal detected.")

        # 4. Write bytes with restrictive permissions (owner read/write only)
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        os.chmod(target_path, 0o600)

        logger.info("Stored private file %s for customer #%d (category: %s)",
                    stored_filename, owner_customer_id, category)

        return {
            "file_id": file_uuid,
            "filename": clean_filename,
            "stored_filename": stored_filename,
            "owner_customer_id": owner_customer_id,
            "category": category,
            "size_bytes": len(file_bytes),
            "storage_path": str(target_path),
            "is_private": True,
        }

    def retrieve_file(
        self,
        file_id: str,
        requesting_customer_id: Optional[int] = None,
        is_admin: bool = False,
        file_owner_id: Optional[int] = None,
    ) -> Tuple[bytes, str]:
        """
        Retrieve private file bytes with authorization check.
        """
        # Verify authorization
        if not is_admin:
            if requesting_customer_id is None or file_owner_id is None or requesting_customer_id != file_owner_id:
                raise DatabaseError("Unauthorized: You do not have permission to access this private document.")

        # Locate matching file in storage_dir
        clean_id = security_validator.sanitize_filename(file_id)
        matches = list(self.storage_dir.glob(f"{clean_id}.*"))
        if not matches:
            raise NotFoundError(f"Document {file_id} not found in private storage.")

        target_path = matches[0].resolve()
        if not str(target_path).startswith(str(self.storage_dir.resolve())):
            raise DatabaseError("Security violation: Path traversal detected.")

        with open(target_path, "rb") as f:
            content = f.read()

        return content, matches[0].name


storage_service = PrivateStorageService()

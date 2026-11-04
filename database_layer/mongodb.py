"""
FinTrack - Smart Digital Banking & Loan Management System
MongoDB Atlas & Local NoSQL Integration Layer
File: database_layer/mongodb.py
"""

import datetime
import logging
from typing import Any, Dict, List, Optional
import pymongo
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError

from config.settings import settings

logger = logging.getLogger(__name__)

# Global singleton client
_MONGO_CLIENT: Optional[pymongo.MongoClient] = None
_INDEXES_INITIALIZED = False


def get_mongo_client() -> Optional[pymongo.MongoClient]:
    """
    Get or initialize the reusable PyMongo client.
    Returns None if MongoDB is not configured.
    """
    global _MONGO_CLIENT
    if not settings.is_mongo_configured():
        return None

    if _MONGO_CLIENT is None:
        try:
            _MONGO_CLIENT = pymongo.MongoClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=2500,
                connectTimeoutMS=2500,
                socketTimeoutMS=5000,
                maxPoolSize=20,
                minPoolSize=1,
            )
        except Exception as exc:
            logger.warning("Failed to initialize MongoDB client: %s", exc)
            return None

    return _MONGO_CLIENT


def get_security_collection() -> Optional[pymongo.collection.Collection]:
    """
    Return the `security_logs` collection and ensure indexes are created idempotently.
    """
    global _INDEXES_INITIALIZED
    client = get_mongo_client()
    if client is None:
        return None

    try:
        db = client[settings.MONGO_DB_NAME]
        coll = db["security_logs"]

        if not _INDEXES_INITIALIZED:
            # Ensure unique index on event_id for idempotent delivery
            coll.create_index([("event_id", pymongo.ASCENDING)], unique=True, name="idx_event_id_unique")
            # Query indexes
            coll.create_index([("timestamp", pymongo.DESCENDING)], name="idx_timestamp_desc")
            coll.create_index([("action", pymongo.ASCENDING)], name="idx_action")
            coll.create_index([("customer_id", pymongo.ASCENDING)], name="idx_customer_id")
            _INDEXES_INITIALIZED = True

        return coll
    except Exception as exc:
        logger.warning("MongoDB collection access error: %s", exc)
        return None


def check_mongo_health() -> bool:
    """Check MongoDB availability via quick ping."""
    client = get_mongo_client()
    if client is None:
        return False
    try:
        client.admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as exc:
        logger.info("MongoDB unavailable or ping failed: %s", exc)
        return False


def insert_audit_document(doc: Dict[str, Any]) -> bool:
    """
    Insert a single audit log document into MongoDB security_logs.
    
    Guarantees:
    - Idempotent: If event_id already exists (DuplicateKeyError), treated as successful.
    - Resilient: Never raises uncaught exceptions that could interrupt caller.
    
    Returns:
        True if inserted or already existed, False if MongoDB was unreachable.
    """
    coll = get_security_collection()
    if coll is None:
        logger.warning("Cannot write audit document: MongoDB is unavailable.")
        return False

    # Ensure document has proper ISO timestamp
    doc_copy = dict(doc)
    if "timestamp" in doc_copy and isinstance(doc_copy["timestamp"], str):
        try:
            doc_copy["timestamp"] = datetime.datetime.fromisoformat(
                doc_copy["timestamp"].replace("Z", "+00:00")
            )
        except Exception:
            pass

    try:
        coll.insert_one(doc_copy)
        return True
    except DuplicateKeyError:
        # Idempotency: Document was already written by a previous retry
        logger.info("Audit event %s already recorded in MongoDB (DuplicateKey).", doc.get("event_id"))
        return True
    except PyMongoError as pme:
        logger.error("MongoDB insertion error for event %s: %s", doc.get("event_id"), pme)
        return False
    except Exception as exc:
        logger.error("Unexpected error writing to MongoDB: %s", exc)
        return False


def query_audit_logs(
    filter_criteria: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    skip: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch security logs from MongoDB with search filters and pagination.
    """
    coll = get_security_collection()
    if coll is None:
        return []

    query = filter_criteria or {}
    try:
        cursor = (
            coll.find(query, {"_id": 0})
            .sort("timestamp", pymongo.DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)
    except Exception as exc:
        logger.error("Error querying MongoDB security logs: %s", exc)
        return []


"""
FinTrack - Security Audit Logs API Endpoints (MongoDB Integration)
File: api/routes/audit.py
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import require_admin
from api.schemas import GenericMessageResponse
from database_layer.mongodb import (
    check_mongo_health,
    count_audit_logs,
    get_security_collection,
    query_audit_logs,
)
from database_layer.postgres import fetch_one
from services.audit_service import audit_service
from services.auth_service import AuthUser
from workers.audit_worker import AuditWorker

router = APIRouter(prefix="/api/admin/audit-logs", tags=["Admin Audit Logs"])


@router.get("")
def get_audit_logs(
    action: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    admin: AuthUser = Depends(require_admin),
):
    """Query append-only security audit logs stored in MongoDB Atlas / Community."""
    is_mongo_up = check_mongo_health()

    # Outbox status from PostgreSQL
    outbox_status = fetch_one(
        """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
            COUNT(*) FILTER (WHERE status = 'PROCESSING') AS processing,
            COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered,
            COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
        FROM audit_outbox;
        """
    )

    if not is_mongo_up:
        return {
            "mongo_status": "OFFLINE",
            "message": "MongoDB is currently offline. Outbox events are safely buffered in PostgreSQL.",
            "total_count": 0,
            "logs": [],
            "outbox": outbox_status,
        }

    criteria = {}
    if action:
        criteria["$or"] = [{"action": action}, {"event_type": action}]
    if customer_id:
        criteria["customer_id"] = customer_id
    if account_id:
        criteria["$or"] = [{"account_id": account_id}, {"metadata.account_id": account_id}]

    logs = query_audit_logs(
        filter_criteria=criteria,
        limit=limit,
        skip=skip,
    )
    total_count = count_audit_logs(
        filter_criteria=criteria,
    )

    return {
        "mongo_status": "ONLINE",
        "total_count": total_count,
        "logs": logs,
        "outbox": outbox_status,
        "limit": limit,
        "skip": skip,
    }


@router.get("/{event_id}")
def get_audit_log_by_id(event_id: str, admin: AuthUser = Depends(require_admin)):
    """Retrieve detailed JSON document for a specific audit event."""
    coll = get_security_collection()
    if coll is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MongoDB unavailable.")

    doc = coll.find_one({"event_id": event_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit event {event_id} not found.")

    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


@router.post("/sync", response_model=GenericMessageResponse)
def trigger_outbox_sync(admin: AuthUser = Depends(require_admin)):
    """Run an on-demand synchronization pass from PostgreSQL audit_outbox to MongoDB."""
    audit_service.record_outbox_event(
        "ADMIN_MANUAL_OUTBOX_SYNC",
        {"admin_user_id": admin.user_id, "admin_username": admin.username},
    )
    try:
        worker = AuditWorker()
        processed = worker.run_once()
        return GenericMessageResponse(
            success=True,
            message=f"Transactional Outbox synchronization executed. Processed {processed} event(s).",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sync error: {e}")

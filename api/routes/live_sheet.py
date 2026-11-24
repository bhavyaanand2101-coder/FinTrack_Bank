"""
FinTrack - Real-Time Live Excel Spreadsheet API & SSE Stream
File: api/routes/live_sheet.py

Streams real-time PostgreSQL ACID state changes directly to the browser
(Server-Sent Events) so users see database tables update live like an Excel sheet.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from api.deps import decode_access_token, get_current_user
from database_layer.postgres import fetch_one
from services.auth_service import AuthUser
from services.excel_service import ExcelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live-sheet", tags=["Live Excel Sheet"])


def _authenticate_stream_token(token: str) -> AuthUser:
    """Validate JWT passed via query param for EventSource (SSE) connections."""
    payload = decode_access_token(token)
    user_id = int(payload.get("sub", 0))
    row = fetch_one(
        """
        SELECT u.user_id, u.customer_id, u.username, u.role, u.is_active,
               c.full_name, c.email
        FROM users u
        LEFT JOIN customers c ON u.customer_id = c.customer_id
        WHERE u.user_id = %s;
        """,
        (user_id,),
    )
    if not row or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive session.",
        )
    return AuthUser(
        user_id=row["user_id"],
        customer_id=row["customer_id"],
        username=row["username"],
        role=row["role"],
        is_active=row["is_active"],
        full_name=row["full_name"] or ("System Administrator" if row["role"] == "ADMIN" else row["username"]),
        email=row["email"],
    )


def _build_snapshot_for_user(user: AuthUser) -> dict:
    """Build role-scoped live spreadsheet snapshot (Admin = bank-wide, Customer = strictly own data)."""
    if user.is_admin():
        return ExcelService.get_admin_live_sheet_snapshot()
    if user.customer_id is None:
        raise HTTPException(status_code=400, detail="Customer profile missing.")
    return ExcelService.get_customer_live_sheet_snapshot(user.customer_id)


@router.get("/snapshot")
def get_live_sheet_snapshot(
    since_fingerprint: Optional[str] = Query(default=None),
    user: AuthUser = Depends(get_current_user),
):
    """
    Fetch current live spreadsheet snapshot.
    Pass `since_fingerprint` to skip payload serialization when nothing changed in PostgreSQL.
    """
    current_fp = ExcelService.compute_database_fingerprint()
    if since_fingerprint and since_fingerprint == current_fp:
        return {"changed": False, "fingerprint": current_fp}
    return _build_snapshot_for_user(user)


@router.get("/stream")
async def stream_live_sheet(
    request: Request,
    token: str = Query(..., description="JWT access token for SSE authentication"),
):
    """
    Server-Sent Events (SSE) real-time stream.
    Pushes live spreadsheet updates within ~500ms of any PostgreSQL ACID commit.
    """
    user = _authenticate_stream_token(token)

    async def event_generator():
        last_fp: Optional[str] = None
        heartbeat_counter = 0
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    current_fp = await asyncio.to_thread(ExcelService.compute_database_fingerprint)
                    if current_fp != last_fp:
                        snapshot = await asyncio.to_thread(_build_snapshot_for_user, user)
                        last_fp = snapshot["fingerprint"]
                        payload = json.dumps(snapshot, default=str)
                        yield f"event: snapshot\ndata: {payload}\n\n"
                        heartbeat_counter = 0
                    else:
                        heartbeat_counter += 1
                        if heartbeat_counter >= 20:
                            yield ": heartbeat\n\n"
                            heartbeat_counter = 0
                except Exception as exc:
                    logger.error("Live sheet stream error: %s", exc)
                    yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

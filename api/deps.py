"""
FinTrack - FastAPI Authentication & Dependency Injection Module
File: api/deps.py
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings
from database_layer.postgres import fetch_one
from services.auth_service import AuthUser

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def create_access_token(user: AuthUser) -> str:
    """Create a signed JWT access token for authenticated session."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload: Dict[str, Any] = {
        "sub": str(user.user_id),
        "username": user.username,
        "role": user.role,
        "customer_id": user.customer_id,
        "full_name": user.full_name,
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> AuthUser:
    """Extract, decode, and verify active user from Authorization header."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth.credentials)
    user_id = int(payload.get("sub", 0))

    query = """
        SELECT 
            u.user_id, u.customer_id, u.username, u.role, u.is_active,
            c.full_name, c.email
        FROM users u
        LEFT JOIN customers c ON u.customer_id = c.customer_id
        WHERE u.user_id = %s;
    """
    row = fetch_one(query, (user_id,))
    if not row or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthUser(
        user_id=row["user_id"],
        customer_id=row["customer_id"],
        username=row["username"],
        role=row["role"],
        is_active=row["is_active"],
        full_name=row.get("full_name"),
        email=row.get("email"),
    )


def require_customer(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Ensure authenticated user is a verified Customer."""
    if not current_user.is_customer() or current_user.customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer privileges required for this resource.",
        )
    return current_user


def require_admin(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Ensure authenticated user is an Administrator."""
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required for this resource.",
        )
    return current_user


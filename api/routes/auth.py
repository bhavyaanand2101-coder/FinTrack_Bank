"""
FinTrack - Authentication API Endpoints
File: api/routes/auth.py
"""

import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from api.deps import create_access_token, get_current_user
from api.schemas import (
    GenericMessageResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserOut,
)
from database_layer.postgres import DatabaseError
from services.auth_service import AuthService, AuthUser

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request):
    """Authenticate user with username and password, return JWT token."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Unknown Client")

    try:
        auth_user = AuthService.login(
            username=req.username,
            plain_password=req.password,
            ip_address=client_ip,
            device_info=user_agent,
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    token = create_access_token(auth_user)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(
            user_id=auth_user.user_id,
            customer_id=auth_user.customer_id,
            username=auth_user.username,
            role=auth_user.role,
            full_name=auth_user.full_name,
            email=auth_user.email,
        ),
    )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, request: Request):
    """Register a new customer account with default savings account and initial deposit."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        customer_id, user_id, account_id = AuthService.register_customer(
            full_name=req.full_name,
            email=req.email,
            phone=req.phone,
            username=req.username,
            plain_password=req.password,
            initial_deposit=req.initial_deposit,
            ip_address=client_ip,
        )
    except (ValueError, DatabaseError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    auth_user = AuthUser(
        user_id=user_id,
        customer_id=customer_id,
        username=req.username.strip().lower(),
        role="CUSTOMER",
        is_active=True,
        full_name=req.full_name.strip(),
        email=req.email.strip().lower(),
        login_time=time.time(),
    )

    token = create_access_token(auth_user)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(
            user_id=auth_user.user_id,
            customer_id=auth_user.customer_id,
            username=auth_user.username,
            role=auth_user.role,
            full_name=auth_user.full_name,
            email=auth_user.email,
        ),
    )


@router.get("/me", response_model=UserOut)
def get_current_user_profile(user: AuthUser = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return UserOut(
        user_id=user.user_id,
        customer_id=user.customer_id,
        username=user.username,
        role=user.role,
        full_name=user.full_name,
        email=user.email,
    )


@router.post("/logout", response_model=GenericMessageResponse)
def logout(user: AuthUser = Depends(get_current_user)):
    """Acknowledge logout on server side."""
    return GenericMessageResponse(success=True, message="Successfully logged out.")


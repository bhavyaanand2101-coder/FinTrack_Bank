"""
FinTrack - Pydantic Request & Response Data Schemas
File: api/schemas.py
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Authentication Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    user_id: int
    customer_id: Optional[int] = None
    username: str
    role: str
    full_name: Optional[str] = None
    email: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., min_length=5, max_length=254)
    phone: str = Field(..., min_length=10, max_length=15)
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8)
    initial_deposit: Decimal = Field(default=Decimal("1000.00"), ge=Decimal("500.00"))


# ---------------------------------------------------------------------------
# Account Schemas
# ---------------------------------------------------------------------------

class AccountOut(BaseModel):
    account_id: int
    customer_id: int
    account_type: str
    balance: Decimal
    currency: str
    is_frozen: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountSummaryOut(BaseModel):
    account_id: int
    customer_id: int
    customer_name: Optional[str] = None
    account_type: str
    balance: Decimal
    is_frozen: bool
    total_incoming_amount: Decimal = Decimal("0.00")
    total_outgoing_amount: Decimal = Decimal("0.00")
    total_transactions_count: int = 0


class FreezeAccountRequest(BaseModel):
    freeze: bool


# ---------------------------------------------------------------------------
# Transfer & Transaction Schemas
# ---------------------------------------------------------------------------

class TransferRequest(BaseModel):
    sender_account_id: int
    receiver_account_id: int
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    description: str = Field(default="Fund Transfer", max_length=200)
    idempotency_key: Optional[str] = None


class TransferResponse(BaseModel):
    status: str
    transaction_id: Optional[int] = None
    alert_id: Optional[int] = None
    amount: Decimal
    is_replay: bool = False
    message: str


class RecipientLookupResponse(BaseModel):
    account_id: int
    customer_name: str
    account_type: str
    is_frozen: bool


class TransactionOut(BaseModel):
    transaction_id: int
    idempotency_key: str
    sender_account_id: int
    sender_name: str
    receiver_account_id: int
    receiver_name: str
    amount: Decimal
    currency: str
    status: str
    description: Optional[str] = None
    transaction_date: datetime
    direction: Optional[str] = None


class RunningBalanceEntry(BaseModel):
    entry_id: int
    account_id: int
    entry_type: str
    amount: Decimal
    created_at: datetime
    running_balance: Decimal


class MonthlySpendingItem(BaseModel):
    month_label: str
    total_monthly_outgoing: Decimal
    transfer_count: int


# ---------------------------------------------------------------------------
# Loan Schemas
# ---------------------------------------------------------------------------

class LoanCalculateRequest(BaseModel):
    annual_income: Decimal = Field(..., gt=Decimal("0.00"))
    requested_amount: Decimal = Field(..., gt=Decimal("0.00"))
    credit_score: int = Field(..., ge=300, le=900)


class LoanCalculateResponse(BaseModel):
    is_eligible: bool
    status: str
    max_eligible_amount: Decimal
    suggested_interest_rate: Decimal
    requested_amount: Decimal
    annual_income: Decimal
    credit_score: int


class LoanApplyRequest(BaseModel):
    requested_amount: Decimal = Field(..., gt=Decimal("0.00"))
    annual_income: Decimal = Field(..., gt=Decimal("0.00"))
    credit_score: int = Field(..., ge=300, le=900)


class LoanOut(BaseModel):
    loan_id: int
    customer_id: int
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    requested_amount: Decimal
    annual_income: Decimal
    credit_score: int
    interest_rate: Decimal
    status: str
    applied_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_username: Optional[str] = None


class AdminDecisionRequest(BaseModel):
    decision: Optional[str] = Field(default="APPROVE", pattern="^(APPROVE|REJECT|APPROVED|REJECTED)$")
    notes: Optional[str] = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# Fraud & Compliance Schemas
# ---------------------------------------------------------------------------

class FraudAlertOut(BaseModel):
    alert_id: int
    transaction_id: int
    account_id: int
    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None
    amount: Optional[Decimal] = None
    risk_score: Decimal
    reason: str
    alert_status: str
    alert_created_at: datetime
    reviewed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Admin & Reports Schemas
# ---------------------------------------------------------------------------

class AdminDashboardKPIs(BaseModel):
    total_customers: int
    total_accounts: int
    total_transactions: int
    total_volume: Decimal
    pending_loans: int
    pending_fraud_reviews: int


class CustomerDetailOut(BaseModel):
    customer_id: int
    full_name: str
    email: str
    phone: str
    created_at: datetime
    accounts: List[AccountOut] = []


class GenericMessageResponse(BaseModel):
    success: bool
    message: str

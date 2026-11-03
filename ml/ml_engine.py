"""
FinTrack - Smart Digital Banking & Loan Management System
AI/ML Fraud Detection Engine
Statistical Anomaly Detection using Z-Score & Configurable Hard Rules
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
import math
from typing import Any, List, Optional, Union
import numpy as np

from config.settings import settings


@dataclass
class FraudCheckResult:
    """Structured response from the fraud detection engine."""
    is_fraud: bool
    risk_score: float
    reason: str
    method: str
    status: str  # 'FLAGGED' or 'CLEARED'
    mean_amount: Optional[float] = None
    std_dev: Optional[float] = None
    z_score: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert dataclass to dictionary."""
        return asdict(self)


class FraudDetector:
    """
    Statistical and Rule-based Anomaly Detection Engine for Financial Transfers.
    
    Z-Score Formula:
        Z = (X - mean) / standard_deviation
    
    Rules & Constraints:
    - Analyzes past successful outgoing transfers for the customer.
    - Excludes the current transaction from historical training baseline.
    - Requires at least `min_samples` (default: 5) historical observations for statistical modeling.
    - If history has < 5 observations: uses Cold-Start Rule-based fallback.
    - If standard deviation == 0: uses Zero-Variance Fallback.
    - If absolute Z-Score > threshold (default: 3.0): flags as statistical anomaly.
    - Hard rule: Any transfer >= FRAUD_THRESHOLD (default: INR 10,000) is flagged.
    - The ML model is advisory to the database transaction engine and never independently
      authorizes suspicious transfers.
    """

    def __init__(
        self,
        fraud_threshold: Optional[Union[Decimal, float]] = None,
        z_score_threshold: Optional[float] = None,
        min_samples: Optional[int] = None,
        history_window: int = 50,
    ):
        self.fraud_threshold = (
            Decimal(str(fraud_threshold))
            if fraud_threshold is not None
            else settings.FRAUD_THRESHOLD
        )
        self.z_score_threshold = (
            float(z_score_threshold)
            if z_score_threshold is not None
            else settings.Z_SCORE_THRESHOLD
        )
        self.min_samples = (
            int(min_samples)
            if min_samples is not None
            else settings.MIN_ML_SAMPLES
        )
        self.history_window = history_window

    def evaluate_transfer(
        self,
        amount: Union[Decimal, float, int],
        historical_amounts: List[Union[Decimal, float, int]],
    ) -> FraudCheckResult:
        """
        Evaluate an outgoing transfer for anomaly / fraud risk.

        Args:
            amount: Amount of the current transfer (must be positive).
            historical_amounts: List of amounts from previous successful outgoing transfers.

        Returns:
            FraudCheckResult with is_fraud, risk_score, reason, method, and status.

        Raises:
            ValueError: If amount is negative, zero, or invalid.
        """
        # Validate amount
        if amount is None:
            raise ValueError("Transfer amount cannot be None.")

        try:
            dec_amount = Decimal(str(amount))
        except Exception as e:
            raise ValueError(f"Invalid transfer amount: {amount}") from e

        if dec_amount <= Decimal("0"):
            raise ValueError("Transfer amount must be strictly greater than zero.")

        float_amount = float(dec_amount)

        # 1. Hard Rule Check: Large transfer threshold (e.g., >= 10,000 INR)
        if dec_amount >= self.fraud_threshold:
            return FraudCheckResult(
                is_fraud=True,
                risk_score=round(float(dec_amount / self.fraud_threshold), 4),
                reason=f"Transfer amount (INR {dec_amount:,.2f}) exceeds or meets mandatory fraud review threshold (INR {self.fraud_threshold:,.2f}).",
                method="HARD_RULE_THRESHOLD",
                status="FLAGGED",
            )

        # Sanitize and truncate historical data to recent window
        valid_history: List[float] = []
        for h in historical_amounts:
            try:
                h_val = float(Decimal(str(h)))
                if h_val > 0 and not math.isnan(h_val) and not math.isinf(h_val):
                    valid_history.append(h_val)
            except Exception:
                continue

        # Window cutoff
        if len(valid_history) > self.history_window:
            valid_history = valid_history[-self.history_window :]

        # 2. Cold-Start Check: Insufficient historical data (< min_samples)
        if len(valid_history) < self.min_samples:
            # Under threshold because hard rule already checked above
            return FraudCheckResult(
                is_fraud=False,
                risk_score=round(float_amount / float(self.fraud_threshold), 4),
                reason=f"Cold-start: Only {len(valid_history)} past transactions (minimum {self.min_samples} required). Amount is below hard threshold.",
                method="COLD_START_RULE",
                status="CLEARED",
            )

        # Compute Mean and Sample Standard Deviation
        hist_arr = np.array(valid_history, dtype=np.float64)
        mean_val = float(np.mean(hist_arr))
        # Use ddof=1 for sample standard deviation
        std_val = float(np.std(hist_arr, ddof=1))

        # 3. Zero-Variance Fallback (Standard deviation is 0.0)
        if std_val == 0.0 or math.isclose(std_val, 0.0, abs_tol=1e-8):
            # Safe heuristic: flag if amount exceeds 2x historical constant amount
            if float_amount > (mean_val * 2.0):
                return FraudCheckResult(
                    is_fraud=True,
                    risk_score=round(float_amount / mean_val, 4) if mean_val > 0 else 5.0,
                    reason=f"Zero-variance history: Transfer amount (INR {float_amount:,.2f}) is more than 2x the standard transfer size (INR {mean_val:,.2f}).",
                    method="ZERO_VARIANCE_FALLBACK",
                    status="FLAGGED",
                    mean_amount=round(mean_val, 2),
                    std_dev=0.0,
                    z_score=None,
                )
            else:
                return FraudCheckResult(
                    is_fraud=False,
                    risk_score=round(float_amount / (mean_val * 2.0), 4) if mean_val > 0 else 0.1,
                    reason="Zero-variance history: Transfer amount is within safe range of regular transfers.",
                    method="ZERO_VARIANCE_FALLBACK",
                    status="CLEARED",
                    mean_amount=round(mean_val, 2),
                    std_dev=0.0,
                    z_score=None,
                )

        # 4. Statistical Z-Score Calculation
        z_score = (float_amount - mean_val) / std_val

        # Risk score normalized
        risk_score = round(max(0.0, z_score), 4)

        if abs(z_score) > self.z_score_threshold:
            return FraudCheckResult(
                is_fraud=True,
                risk_score=risk_score,
                reason=(
                    f"Statistical anomaly detected: Transfer of INR {float_amount:,.2f} has Z-score of {z_score:+.2f} "
                    f"(exceeds threshold of {self.z_score_threshold}). Mean: INR {mean_val:,.2f}, StdDev: INR {std_val:,.2f}."
                ),
                method="Z_SCORE",
                status="FLAGGED",
                mean_amount=round(mean_val, 2),
                std_dev=round(std_val, 2),
                z_score=round(z_score, 4),
            )

        return FraudCheckResult(
            is_fraud=False,
            risk_score=risk_score,
            reason=f"Normal transfer pattern: Z-score is {z_score:+.2f} (within +/-{self.z_score_threshold}).",
            method="Z_SCORE",
            status="CLEARED",
            mean_amount=round(mean_val, 2),
            std_dev=round(std_val, 2),
            z_score=round(z_score, 4),
        )


# Global default detector instance
fraud_detector = FraudDetector()


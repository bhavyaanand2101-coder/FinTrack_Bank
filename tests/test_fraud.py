"""
FinTrack - AI/ML Fraud Anomaly Detection Unit Tests
File: tests/test_fraud.py
"""

from decimal import Decimal
import pytest

from ml.ml_engine import FraudCheckResult, FraudDetector, fraud_detector


def test_cold_start_fallback():
    # Only 2 past transactions (< 5 required)
    history = [500, 600]
    result = fraud_detector.evaluate_transfer(750, history)

    assert result.method == "COLD_START_RULE"
    assert result.is_fraud is False
    assert result.status == "CLEARED"


def test_normal_transaction_within_distribution():
    # Regular transfer around 1,000 INR
    history = [950, 1020, 980, 1050, 1010, 990, 1030]
    result = fraud_detector.evaluate_transfer(1040, history)

    assert result.method == "Z_SCORE"
    assert result.is_fraud is False
    assert result.status == "CLEARED"
    assert abs(result.z_score) < 3.0


def test_hard_rule_large_transfer():
    # Any transfer >= 10,000 INR must be flagged immediately
    history = [800, 850, 900, 820, 810]
    result = fraud_detector.evaluate_transfer(10000, history)

    assert result.is_fraud is True
    assert result.status == "FLAGGED"
    assert result.method == "HARD_RULE_THRESHOLD"

    result_above = fraud_detector.evaluate_transfer(25000, history)
    assert result_above.is_fraud is True
    assert result_above.status == "FLAGGED"


def test_zero_variance_fallback():
    # Exactly identical historical transfers: standard deviation is 0.0
    history = [500, 500, 500, 500, 500, 500]

    # Transfer of 550 INR: safe within reasonable multiple
    res_safe = fraud_detector.evaluate_transfer(550, history)
    assert res_safe.method == "ZERO_VARIANCE_FALLBACK"
    assert res_safe.is_fraud is False
    assert res_safe.status == "CLEARED"

    # Transfer of 1,500 INR: more than 2x mean (500) -> flagged
    res_outlier = fraud_detector.evaluate_transfer(1500, history)
    assert res_outlier.method == "ZERO_VARIANCE_FALLBACK"
    assert res_outlier.is_fraud is True
    assert res_outlier.status == "FLAGGED"


def test_statistical_z_score_outlier():
    # History with mean ~500, std dev ~25
    history = [500, 510, 490, 505, 495, 500, 515, 485]
    # Amount 2,000 INR has Z-score > 50 -> extreme anomaly
    result = fraud_detector.evaluate_transfer(2000, history)

    assert result.method == "Z_SCORE"
    assert result.is_fraud is True
    assert result.status == "FLAGGED"
    assert result.z_score > 3.0


def test_invalid_input_handling():
    history = [500, 600, 700, 800, 900]

    with pytest.raises(ValueError, match="strictly greater than zero"):
        fraud_detector.evaluate_transfer(-100, history)

    with pytest.raises(ValueError, match="strictly greater than zero"):
        fraud_detector.evaluate_transfer(0, history)

    with pytest.raises(ValueError, match="cannot be None"):
        fraud_detector.evaluate_transfer(None, history)

    with pytest.raises(ValueError, match="Invalid transfer amount"):
        fraud_detector.evaluate_transfer("invalid_amount_abc", history)

"""
FinTrack - Smart Digital Banking & Loan Management System
Configuration and Environment Settings Module
"""

import os
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if it exists
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    """Application runtime configuration settings."""

    # PostgreSQL Database URL
    POSTGRES_URI: str = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/fintrack?sslmode=prefer"
    )

    # MongoDB Atlas Connection URL (Optional)
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "fintrack_db")

    # PostgreSQL Connection Pooling
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "10"))
    DB_TIMEOUT_SECONDS: int = int(os.getenv("DB_TIMEOUT_SECONDS", "10"))

    # Fraud Detection Rules & ML
    # Strict Decimal for currency amounts
    FRAUD_THRESHOLD: Decimal = Decimal(os.getenv("FRAUD_THRESHOLD", "10000.00"))
    Z_SCORE_THRESHOLD: float = float(os.getenv("Z_SCORE_THRESHOLD", "3.0"))
    MIN_ML_SAMPLES: int = int(os.getenv("MIN_ML_SAMPLES", "5"))

    # Security & Session
    SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "fintrack-dev-secret-key-32-bytes-long!")

    @classmethod
    def is_mongo_configured(cls) -> bool:
        """Check if MongoDB URI is provided and non-empty."""
        return bool(cls.MONGO_URI and cls.MONGO_URI.strip() and not cls.MONGO_URI.startswith("mongodb+srv://<username>"))

    @classmethod
    def validate(cls) -> dict[str, bool]:
        """Validate critical configuration parameters."""
        status = {
            "postgres_configured": bool(cls.POSTGRES_URI and cls.POSTGRES_URI.strip()),
            "mongo_configured": cls.is_mongo_configured(),
            "pool_bounds_valid": 1 <= cls.DB_POOL_MIN <= cls.DB_POOL_MAX,
            "thresholds_valid": cls.FRAUD_THRESHOLD > 0 and cls.Z_SCORE_THRESHOLD > 0,
        }
        return status


settings = Settings()


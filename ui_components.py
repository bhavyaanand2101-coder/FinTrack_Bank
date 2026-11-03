"""
FinTrack - Smart Digital Banking & Loan Management System
UI Utilities, Custom Styles & Session Helper Module
File: ui_components.py
"""

import datetime
from decimal import Decimal
import time
from typing import Any, Dict, List, Optional
import streamlit as st

from config.settings import settings
from database_layer.db import check_postgres_health
from database_layer.mongodb import check_mongo_health
from services.auth_service import AuthUser


def inject_custom_styles():
    """Inject modern fintech navy and clean blue styling into Streamlit."""
    st.markdown(
        """
        <style>
        /* Base typography & palette */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Top header bar accent */
        .fintrack-brand-header {
            background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
            color: #FFFFFF;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
        }

        /* Financial metric card */
        .metric-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            margin-bottom: 16px;
        }
        .metric-title {
            font-size: 13px;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        .metric-value {
            font-size: 26px;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.2;
        }
        .metric-sub {
            font-size: 12px;
            color: #10B981;
            margin-top: 4px;
        }

        /* Status Badges */
        .badge-success {
            background-color: #DEF7EC;
            color: #03543F;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-flagged {
            background-color: #FEF3C7;
            color: #92400E;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-failed {
            background-color: #FDE8E8;
            color: #9B1C1C;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-pending {
            background-color: #E1EFFE;
            color: #1E429F;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        /* Primary button styling */
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    """Render universal sidebar with session info, system status, and navigation."""
    with st.sidebar:
        st.markdown("### 🏦 **FinTrack**")
        st.caption("Smart Digital Banking & Loan System")
        st.divider()

        user: Optional[AuthUser] = st.session_state.get("authenticated_user")
        if user:
            # Check session expiry
            if user.is_session_expired():
                st.warning("⚠️ Session expired due to inactivity. Please log in again.")
                st.session_state.clear()
                st.rerun()

            st.markdown(f"**👤 {user.full_name or user.username}**")
            role_badge = "🛡️ Administrator" if user.is_admin() else "👤 Customer"
            st.caption(f"Role: {role_badge}")
            if user.customer_id:
                st.caption(f"Customer ID: #{user.customer_id}")

            st.divider()

            # Navigation Links
            st.markdown("**Navigation**")
            st.page_link("app.py", label="Home / Overview", icon="🏠")
            if user.is_customer():
                st.page_link("pages/1_Dashboard.py", label="Account Dashboard", icon="📊")
                st.page_link("pages/2_Transfers.py", label="Fund Transfers", icon="💸")
                st.page_link("pages/3_Loans.py", label="Loan Application", icon="📝")
            elif user.is_admin():
                st.page_link("pages/4_Admin_Dashboard.py", label="Admin Overview", icon="📈")
                st.page_link("pages/5_Loan_Management.py", label="Loan Approvals", icon="📑")
                st.page_link("pages/6_Fraud_Monitoring.py", label="Fraud Detection", icon="🚨")
                st.page_link("pages/7_Audit_Logs.py", label="Security Audit Logs", icon="🔒")

            st.divider()
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
                st.session_state.clear()
                st.rerun()
        else:
            st.page_link("app.py", label="Sign In / Register", icon="🔑")
            st.info("Please log in to access your accounts or management dashboard.")

        st.divider()
        # Database connectivity indicators
        pg_ok = check_postgres_health()
        mongo_ok = check_mongo_health()

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"PostgreSQL: {'🟢 Active' if pg_ok else '🔴 Offline'}")
        with col2:
            st.caption(f"MongoDB: {'🟢 Active' if mongo_ok else '🟡 Pending'}")


def require_auth(role: Optional[str] = None) -> AuthUser:
    """
    Enforce route protection. Redirects to app.py if unauthenticated or unauthorized.
    """
    user: Optional[AuthUser] = st.session_state.get("authenticated_user")
    if not user:
        st.warning("⚠️ Access Denied: Please log in to view this page.")
        st.stop()

    if user.is_session_expired():
        st.warning("⚠️ Session expired. Please log in again.")
        st.session_state.clear()
        st.stop()

    if role == "ADMIN" and not user.is_admin():
        st.error("🚫 Access Denied: Administrator privileges required.")
        st.stop()

    if role == "CUSTOMER" and not user.is_customer():
        st.error("🚫 Customer account required for this page.")
        st.stop()

    return user

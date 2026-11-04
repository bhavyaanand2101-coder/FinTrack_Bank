"""
FinTrack - Smart Digital Banking & Loan Management System
Main Entrypoint & Authentication Portal
File: app.py
"""

from decimal import Decimal
import streamlit as st

from database_layer.db import check_postgres_health
from database_layer.mongodb import check_mongo_health
from services.auth_service import AuthUser, auth_service
from ui_components import inject_custom_styles, render_sidebar

# Streamlit Page Config
st.set_page_config(
    page_title="FinTrack – Digital Banking",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_styles()
render_sidebar()

# Session State Initialization
if "authenticated_user" not in st.session_state:
    st.session_state["authenticated_user"] = None

user: AuthUser = st.session_state["authenticated_user"]

# ============================================================================
# Main Page Header
# ============================================================================
st.markdown(
    """
    <div class="fintrack-brand-header">
        <h1 style="margin: 0; font-size: 28px; font-weight: 700;">🏦 FinTrack Banking Simulator</h1>
        <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 15px;">
            Academic Digital Banking, Concurrency Control, AI/ML Anomaly Detection & NoSQL Auditing System
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# VIEW 1: Authenticated User Welcome Screen
# ============================================================================
if user:
    st.success(f"👋 Welcome back, **{user.full_name or user.username}**! You are logged in as **{user.role}**.")

    col1, col2, col3 = st.columns(3)
    if user.is_customer():
        with col1:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">📊 Account Overview</div>
                    <p style="font-size: 13px; color: #475569;">Check account balances, running balances and monthly spending analysis.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/1_Dashboard.py", label="Open Dashboard", icon="📊", use_container_width=True)

        with col2:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">💸 Fund Transfers</div>
                    <p style="font-size: 13px; color: #475569;">Atomic transfers with ML fraud detection & double-entry ledger bookkeeping.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/2_Transfers.py", label="Transfer Funds", icon="💸", use_container_width=True)

        with col3:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">📝 Loan Center</div>
                    <p style="font-size: 13px; color: #475569;">Check credit eligibility, calculated interest rates, and apply for personal loans.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/3_Loans.py", label="Apply for Loan", icon="📝", use_container_width=True)

    elif user.is_admin():
        with col1:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">📈 Management Console</div>
                    <p style="font-size: 13px; color: #475569;">Monitor active customers, accounts, transfer volume and system statistics.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/4_Admin_Dashboard.py", label="Admin Console", icon="📈", use_container_width=True)

        with col2:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">🚨 Compliance & Fraud</div>
                    <p style="font-size: 13px; color: #475569;">Review flagged suspicious transfers, Z-score risk alerts, and approve or reject.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/6_Fraud_Monitoring.py", label="Review Fraud Alerts", icon="🚨", use_container_width=True)

        with col3:
            st.markdown(
                """
                <div class="metric-card">
                    <div class="metric-title">🔒 MongoDB Audit Logs</div>
                    <p style="font-size: 13px; color: #475569;">Inspect transactional outbox security logs streamed into MongoDB Atlas.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/7_Audit_Logs.py", label="Inspect Security Logs", icon="🔒", use_container_width=True)

# ============================================================================
# VIEW 2: Unauthenticated Sign In & Registration Tabs
# ============================================================================
else:
    tab_login, tab_register, tab_demo = st.tabs(["🔑 Sign In", "📝 Register New Customer", "💡 Demo Credentials"])

    with tab_login:
        st.subheader("Secure Access Portal")
        col_form, col_info = st.columns([1.2, 1])

        with col_form:
            with st.form("login_form", clear_on_submit=False):
                username_input = st.text_input("Username", placeholder="e.g. arun_kumar or admin")
                password_input = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                if submitted:
                    if not username_input or not password_input:
                        st.error("Please enter both username and password.")
                    else:
                        try:
                            auth_user = auth_service.login(username_input, password_input)
                            st.session_state["authenticated_user"] = auth_user
                            st.success(f"Login successful! Welcome {auth_user.username}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Authentication Failed: {e}")

        with col_info:
            st.markdown(
                """
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 20px; border-radius: 8px;">
                    <h4 style="margin-top:0; color: #0F172A;">Security Guarantees</h4>
                    <ul style="font-size: 13px; color: #475569; padding-left: 20px;">
                        <li><strong>Argon2id Hashing:</strong> Military-grade memory-hard password verification.</li>
                        <li><strong>Brute-Force Throttling:</strong> Temporary lockout after 5 consecutive failures.</li>
                        <li><strong>Zero Plaintext Storage:</strong> Passwords are never logged or persisted unhashed.</li>
                        <li><strong>RBAC:</strong> Separation between Customer and Administrator roles.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_register:
        st.subheader("Create a New Bank Account")
        with st.form("registration_form"):
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                reg_name = st.text_input("Full Name", placeholder="e.g. Ramesh Iyer")
                reg_email = st.text_input("Email Address", placeholder="ramesh@example.com")
                reg_phone = st.text_input("Phone Number", placeholder="+919812345678")
            with col_r2:
                reg_user = st.text_input("Desired Username", placeholder="e.g. ramesh_iyer")
                reg_pass = st.text_input("Password (min 8 chars)", type="password")
                reg_deposit = st.number_input("Initial Deposit (INR)", min_value=100.0, max_value=500000.0, value=5000.0, step=500.0)

            reg_submit = st.form_submit_button("Register Account", type="primary", use_container_width=True)

            if reg_submit:
                try:
                    c_id, u_id, a_id = auth_service.register_customer(
                        full_name=reg_name,
                        email=reg_email,
                        phone=reg_phone,
                        username=reg_user,
                        plain_password=reg_pass,
                        initial_deposit=Decimal(str(reg_deposit)),
                    )
                    st.success(f"🎉 Account successfully created! Customer #{c_id}, User #{u_id}, Savings Account #{a_id} with initial balance of INR {reg_deposit:,.2f}.")
                    st.info("You can now sign in using your username and password.")
                except Exception as ex:
                    st.error(f"Registration Error: {ex}")

    with tab_demo:
        st.subheader("Documented Academic Demo Credentials")
        st.markdown(
            """
            | Role | Username | Password | Account ID | Default Balance | Description |
            | :--- | :--- | :--- | :--- | :--- | :--- |
            | **Administrator** | `admin` | `AdminPassword123!` | N/A | N/A | Full Administrative & Compliance Access |
            | **Customer 1** | `arun_kumar` | `Customer123!` | `1001` (Savings)<br>`1002` (Checking) | INR 74,500.00<br>INR 25,000.00 | Active transfer history, approved loan |
            | **Customer 2** | `priya_sharma` | `Customer123!` | `1003` (Savings)<br>`1004` (Checking) | INR 112,000.00<br>INR 45,000.00 | High credit score (810), approved loan |
            | **Customer 3** | `rohit_verma` | `Customer123!` | `1005` (Savings) | INR 18,500.00 | Rejected loan & rejected fraud record |
            | **Customer 4** | `ananya_singh` | `Customer123!` | `1006` (Savings)<br>`1007` (Checking) | INR 52,000.00<br>INR 15,000.00 | Pending loan application (INR 100k) |
            | **Customer 5** | `vikram_patel` | `Customer123!` | `1008` (Savings) | INR 88,000.00 | Active outgoing transfers & open fraud alert |
            | **Customer 10** | `amit_gupta` | `Customer123!` | `1016` (Checking) | INR 5,000.00 | Dormant account with zero transactions (Query 5) |
            """
        )


"""
FinTrack - Smart Digital Banking & Loan Management System
Administrator Overview & Analytics Dashboard
File: pages/4_Admin_Dashboard.py
"""

from decimal import Decimal
import pandas as pd
import streamlit as st

from database_layer.db import check_postgres_health
from database_layer.mongodb import check_mongo_health
from database_layer.postgres import execute_scalar, fetch_all, fetch_one
from ui_components import inject_custom_styles, render_sidebar, require_auth

st.set_page_config(page_title="Admin Console – FinTrack", page_icon="📈", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="ADMIN")

st.title("📈 Bank Administration Console")
st.caption(f"Logged in as Administrator: **{user.username}**")

# Top KPI Metric Calculations from PostgreSQL
try:
    total_customers = execute_scalar("SELECT COUNT(*) FROM customers;") or 0
    total_accounts = execute_scalar("SELECT COUNT(*) FROM accounts;") or 0
    tx_stats = fetch_one(
        """
        SELECT 
            COUNT(transaction_id) AS total_count,
            COALESCE(SUM(amount), 0.00) AS total_amount
        FROM transactions
        WHERE status = 'SUCCESS';
        """
    )
    pending_loans_count = execute_scalar("SELECT COUNT(*) FROM loans WHERE status = 'PENDING';") or 0
    open_alerts_count = execute_scalar("SELECT COUNT(*) FROM fraud_alerts WHERE status = 'OPEN';") or 0
except Exception as ex:
    st.error(f"Error fetching system KPIs: {ex}")
    st.stop()

# Metric Cards
m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-title">Customers</div><div class="metric-value">{total_customers}</div></div>""",
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-title">Accounts</div><div class="metric-value">{total_accounts}</div></div>""",
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-title">Transfers (Success)</div><div class="metric-value">{tx_stats['total_count']}</div></div>""",
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-title">Volume Settled</div><div class="metric-value">₹{float(tx_stats['total_amount']):,.0f}</div></div>""",
        unsafe_allow_html=True,
    )
with m5:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-title">Pending Loans</div><div class="metric-value" style="color: {'#DC2626' if pending_loans_count > 0 else '#059669'};">{pending_loans_count}</div></div>""",
        unsafe_allow_html=True,
    )
with m6:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-title">Fraud Alerts</div><div class="metric-value" style="color: {'#DC2626' if open_alerts_count > 0 else '#059669'};">{open_alerts_count}</div></div>""",
        unsafe_allow_html=True,
    )

st.divider()

# Advanced SQL Demonstration Panels
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏆 Top Five Customers by Outgoing Volume")
    st.caption("Demonstrating Advanced Query 4: `GROUP BY, SUM, ORDER BY, LIMIT`")
    top_cust_query = """
        SELECT 
            c.customer_id,
            c.full_name,
            c.email,
            COUNT(t.transaction_id) AS successful_transfers_count,
            SUM(t.amount) AS total_outgoing_volume
        FROM customers c
        JOIN accounts a ON c.customer_id = a.customer_id
        JOIN transactions t ON a.account_id = t.sender_account_id
        WHERE t.status = 'SUCCESS'
        GROUP BY c.customer_id, c.full_name, c.email
        ORDER BY total_outgoing_volume DESC
        LIMIT 5;
    """
    top_customers = fetch_all(top_cust_query)
    if top_customers:
        df_top = pd.DataFrame(top_customers)
        df_top["Volume (INR)"] = df_top["total_outgoing_volume"].apply(lambda v: f"₹{float(v):,.2f}")
        st.dataframe(
            df_top[["customer_id", "full_name", "successful_transfers_count", "Volume (INR)"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No successful outgoing transfers found.")

with col_right:
    st.subheader("💤 Dormant Accounts (Zero Transaction History)")
    st.caption("Demonstrating Advanced Query 5: `LEFT JOIN ... IS NULL`")
    dormant_query = """
        SELECT 
            a.account_id,
            a.account_type,
            a.balance,
            c.customer_id,
            c.full_name,
            c.email
        FROM accounts a
        JOIN customers c ON a.customer_id = c.customer_id
        LEFT JOIN transactions t_send ON a.account_id = t_send.sender_account_id
        LEFT JOIN transactions t_recv ON a.account_id = t_recv.receiver_account_id
        WHERE t_send.transaction_id IS NULL AND t_recv.transaction_id IS NULL;
    """
    dormant_accounts = fetch_all(dormant_query)
    if dormant_accounts:
        df_dormant = pd.DataFrame(dormant_accounts)
        df_dormant["Balance (INR)"] = df_dormant["balance"].apply(lambda v: f"₹{float(v):,.2f}")
        st.dataframe(
            df_dormant[["account_id", "full_name", "account_type", "Balance (INR)"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("All accounts currently have transaction activity.")

st.divider()

# System Infrastructure & Outbox Health
st.subheader("⚙️ System Infrastructure & Transactional Outbox State")
outbox_stats = fetch_one(
    """
    SELECT 
        COUNT(*) FILTER (WHERE status = 'PENDING') AS pending_events,
        COUNT(*) FILTER (WHERE status = 'PROCESSING') AS processing_events,
        COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered_events,
        COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_events
    FROM audit_outbox;
    """
)

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.metric("Outbox: Pending Delivery", outbox_stats["pending_events"] or 0)
with s2:
    st.metric("Outbox: In Processing", outbox_stats["processing_events"] or 0)
with s3:
    st.metric("Outbox: Delivered to MongoDB", outbox_stats["delivered_events"] or 0)
with s4:
    st.metric("Outbox: Failed Delivery", outbox_stats["failed_events"] or 0)

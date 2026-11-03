"""
FinTrack - Smart Digital Banking & Loan Management System
Customer Account Dashboard
File: pages/1_Dashboard.py
"""

from decimal import Decimal
import pandas as pd
import streamlit as st

from services.account_service import account_service
from ui_components import inject_custom_styles, render_sidebar, require_auth

st.set_page_config(page_title="Customer Dashboard – FinTrack", page_icon="📊", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="CUSTOMER")

st.title("📊 Customer Financial Dashboard")
st.caption(f"Account holder: **{user.full_name or user.username}** (Customer ID: #{user.customer_id})")

# 1. Fetch customer's accounts
accounts = account_service.get_customer_accounts(user.customer_id)
if not accounts:
    st.warning("No active accounts found for your customer profile. Please contact bank administration.")
    st.stop()

# 2. Account selector
account_options = {
    f"#{acc['account_id']} – {acc['account_type']} (Balance: INR {acc['balance']:,.2f})": acc["account_id"]
    for acc in accounts
}
selected_label = st.selectbox("Select Account", options=list(account_options.keys()))
active_acc_id = account_options[selected_label]
active_acc = account_service.get_account_by_id(active_acc_id, customer_id=user.customer_id)

# 3. Top Balance & Status Metric Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Available Balance</div>
            <div class="metric-value">₹{active_acc['balance']:,.2f}</div>
            <div class="metric-sub">{active_acc['currency']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    status_badge = '<span class="badge-failed">Frozen</span>' if active_acc["is_frozen"] else '<span class="badge-success">Active</span>'
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Account Status</div>
            <div style="margin-top: 8px;">{status_badge}</div>
            <p style="font-size: 12px; color: #64748B; margin-top: 8px;">Type: {active_acc['account_type']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Retrieve account summary metrics from View_Account_Summary
try:
    summary = account_service.get_account_summary_metrics(active_acc_id)
    incoming_total = summary.get("total_incoming_amount", Decimal("0.00"))
    outgoing_total = summary.get("total_outgoing_amount", Decimal("0.00"))
    tx_count = summary.get("total_transactions_count", 0)
except Exception:
    incoming_total = Decimal("0.00")
    outgoing_total = Decimal("0.00")
    tx_count = 0

with col3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Total Incoming</div>
            <div class="metric-value" style="color: #059669;">₹{incoming_total:,.2f}</div>
            <div style="font-size: 12px; color: #64748B; margin-top: 4px;">Credits Received</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Total Outgoing</div>
            <div class="metric-value" style="color: #DC2626;">₹{outgoing_total:,.2f}</div>
            <div style="font-size: 12px; color: #64748B; margin-top: 4px;">Total Debited ({tx_count} transactions)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# 4. Recent Transactions & Running Balance
tab_recent, tab_running, tab_spending = st.tabs([
    "🕒 Recent Activity",
    "📈 Running Balance (Window Query)",
    "📊 Monthly Spending (CTE Query)",
])

with tab_recent:
    st.subheader(f"Recent Transactions for Account #{active_acc_id}")
    recent_txs = account_service.get_account_recent_transactions(active_acc_id, limit=10)
    if not recent_txs:
        st.info("No transaction history recorded for this account yet.")
    else:
        df_tx = pd.DataFrame(recent_txs)
        # Format display columns
        df_display = pd.DataFrame({
            "Tx ID": df_tx["transaction_id"],
            "Date": pd.to_datetime(df_tx["transaction_date"]).dt.strftime("%Y-%m-%d %H:%M"),
            "Counterparty": df_tx.apply(lambda r: r["receiver_name"] if r["direction"] == "DEBIT" else r["sender_name"], axis=1),
            "Type": df_tx["direction"],
            "Amount (INR)": df_tx["amount"].apply(lambda v: f"₹{float(v):,.2f}"),
            "Status": df_tx["status"],
            "Description": df_tx["description"],
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)

with tab_running:
    st.subheader("Running Account Balance (SQL Window Functions)")
    st.caption("Demonstrating Advanced Query 1: `SUM(...) OVER (PARTITION BY account_id ORDER BY created_at)`")
    running_entries = account_service.get_running_balance(active_acc_id, limit=30)
    if not running_entries:
        st.info("No ledger entries found to calculate running balance.")
    else:
        df_run = pd.DataFrame(running_entries)
        # Chronological order for chart
        df_run_chron = df_run.sort_values(by="created_at", ascending=True).copy()
        df_run_chron["timestamp_str"] = pd.to_datetime(df_run_chron["created_at"]).dt.strftime("%b %d, %H:%M")
        df_run_chron["balance_float"] = df_run_chron["running_balance"].astype(float)

        st.line_chart(
            data=df_run_chron,
            x="timestamp_str",
            y="balance_float",
            color="#2563EB",
            use_container_width=True,
        )

        df_run_disp = pd.DataFrame({
            "Entry ID": df_run["entry_id"],
            "Timestamp": pd.to_datetime(df_run["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S"),
            "Entry Type": df_run["entry_type"],
            "Amount (INR)": df_run["amount"].apply(lambda v: f"₹{float(v):,.2f}"),
            "Running Balance (INR)": df_run["running_balance"].apply(lambda v: f"₹{float(v):,.2f}"),
        })
        st.dataframe(df_run_disp, use_container_width=True, hide_index=True)

with tab_spending:
    st.subheader("Monthly Outgoing Spending Breakdown (CTE)")
    st.caption("Demonstrating Advanced Query 2: `WITH monthly_outgoing AS (...)`")
    monthly_data = account_service.get_monthly_spending_analysis(active_acc_id)
    if not monthly_data:
        st.info("No completed outgoing transfers found for monthly breakdown.")
    else:
        df_month = pd.DataFrame(monthly_data)
        df_month["outgoing_float"] = df_month["total_monthly_outgoing"].astype(float)
        st.bar_chart(
            data=df_month,
            x="month_label",
            y="outgoing_float",
            color="#DC2626",
            use_container_width=True,
        )
        st.dataframe(
            pd.DataFrame({
                "Month": df_month["month_label"],
                "Total Outgoing (INR)": df_month["total_monthly_outgoing"].apply(lambda v: f"₹{float(v):,.2f}"),
                "Successful Transfers": df_month["transfer_count"],
            }),
            use_container_width=True,
            hide_index=True,
        )

"""
FinTrack - Smart Digital Banking & Loan Management System
MongoDB Security Audit Log Viewer & Transactional Outbox Monitor
File: pages/7_Audit_Logs.py
"""

import datetime
import json
import math
import pandas as pd
import streamlit as st

from database_layer.mongodb import check_mongo_health, count_audit_logs, query_audit_logs
from database_layer.postgres import fetch_one
from ui_components import inject_custom_styles, render_sidebar, require_auth
from workers.audit_worker import AuditWorker

st.set_page_config(page_title="Audit Logs – FinTrack", page_icon="🔒", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="ADMIN")

st.title("🔒 MongoDB Security Audit Logs")
st.caption("Immutable append-only security logs synchronized via PostgreSQL Transactional Outbox to MongoDB Atlas.")

# MongoDB Status & Manual Worker Sync
mongo_active = check_mongo_health()
col_stat, col_sync = st.columns([2, 1])

with col_stat:
    if mongo_active:
        st.success("🟢 MongoDB Connection Active: Ready to inspect security logs.")
    else:
        st.warning("🟡 MongoDB Connection Unavailable or Offline. Outbox events remain safely buffered in PostgreSQL.")

with col_sync:
    if st.button("🔄 Trigger Outbox Worker Sync", help="Run a manual sync cycle of pending outbox events"):
        with st.spinner("Processing pending outbox events..."):
            try:
                worker = AuditWorker()
                count = worker.run_once()
                st.success(f"Processed batch of {count} event(s).")
                st.rerun()
            except Exception as e:
                st.error(f"Sync error: {e}")

st.divider()

# Outbox buffer status from PostgreSQL
outbox_status = fetch_one(
    """
    SELECT 
        COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
        COUNT(*) FILTER (WHERE status = 'PROCESSING') AS processing,
        COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered,
        COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
    FROM audit_outbox;
    """
)
o1, o2, o3, o4 = st.columns(4)
with o1:
    st.metric("PostgreSQL Outbox Pending", outbox_status["pending"] or 0)
with o2:
    st.metric("Outbox In-Processing", outbox_status["processing"] or 0)
with o3:
    st.metric("Delivered to MongoDB", outbox_status["delivered"] or 0)
with o4:
    st.metric("Delivery Failed Retries", outbox_status["failed"] or 0)

st.divider()

# Search & Filters
st.subheader("Filter & Inspect Security Documents")
f1, f2, f3 = st.columns(3)
with f1:
    action_filter = st.selectbox(
        "Action Type",
        options=[
            "ALL",
            "LOGIN_SUCCESS",
            "LOGIN_FAILED",
            "CUSTOMER_REGISTERED",
            "TRANSFER_SUCCESS",
            "TRANSFER_FLAGGED",
            "LOAN_APPLICATION_SUBMITTED",
            "LOAN_DECISION",
            "FRAUD_ALERT_APPROVED",
            "FRAUD_ALERT_REJECTED",
        ],
    )
with f2:
    customer_id_filter = st.text_input("Customer ID (optional)", placeholder="e.g. 1")
with f3:
    account_id_filter = st.text_input("Account ID (optional)", placeholder="e.g. 1001")

col_d1, col_d2, col_p = st.columns([1.5, 1.5, 1])
with col_d1:
    use_date_filter = st.checkbox("Filter by Date Range", value=False)
    if use_date_filter:
        start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=7))
with col_d2:
    if use_date_filter:
        end_date = st.date_input("End Date", value=datetime.date.today() + datetime.timedelta(days=1))
with col_p:
    page_size = st.selectbox("Page Size", options=[10, 25, 50], index=1)

# Build Mongo query criteria
criteria = {}
if action_filter != "ALL":
    criteria["action"] = action_filter
if customer_id_filter.strip():
    try:
        criteria["customer_id"] = int(customer_id_filter.strip())
    except ValueError:
        pass
if account_id_filter.strip():
    try:
        criteria["account_id"] = int(account_id_filter.strip())
    except ValueError:
        pass

if use_date_filter:
    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)
    criteria["timestamp"] = {"$gte": start_dt, "$lte": end_dt}

# Pagination state
total_matching = count_audit_logs(criteria)
total_pages = max(1, math.ceil(total_matching / page_size))

if "audit_current_page" not in st.session_state:
    st.session_state["audit_current_page"] = 1

# Bound current page
if st.session_state["audit_current_page"] > total_pages:
    st.session_state["audit_current_page"] = total_pages

current_page = st.session_state["audit_current_page"]
skip_count = (current_page - 1) * page_size

# Query MongoDB
logs = query_audit_logs(criteria, limit=page_size, skip=skip_count)

# Pagination Controls
st.markdown(f"**Found {total_matching} total event(s). Showing Page {current_page} of {total_pages}:**")
p_col1, p_col2, p_col3, p_col4 = st.columns([1, 1, 3, 2])
with p_col1:
    if st.button("⬅️ Previous", disabled=(current_page <= 1), use_container_width=True):
        st.session_state["audit_current_page"] -= 1
        st.rerun()
with p_col2:
    if st.button("Next ➡️", disabled=(current_page >= total_pages), use_container_width=True):
        st.session_state["audit_current_page"] += 1
        st.rerun()

if not logs:
    st.info("No audit logs found matching the specified filters.")
else:
    # Summary Table
    table_rows = []
    for log in logs:
        ts = log.get("timestamp", "")
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)[:19]
        table_rows.append({
            "Timestamp": ts_str,
            "Action": log.get("action", "UNKNOWN"),
            "Customer ID": log.get("customer_id") or "—",
            "Account ID": log.get("account_id") or "—",
            "Transaction ID": log.get("transaction_id") or "—",
            "IP Address": log.get("ip_address", "—"),
            "Event ID": str(log.get("event_id", ""))[:8] + "...",
        })

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    st.subheader("Document Deep Inspection")
    for log in logs:
        ts = log.get("timestamp", "")
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)
        ev_id = log.get("event_id", "N/A")
        with st.expander(f"[{ts_str}] {log.get('action', 'LOG')} – Event ID: {ev_id}"):
            st.json(log)

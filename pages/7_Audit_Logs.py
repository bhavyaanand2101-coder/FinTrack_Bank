"""
FinTrack - Smart Digital Banking & Loan Management System
MongoDB Security Audit Log Viewer & Transactional Outbox Monitor
File: pages/7_Audit_Logs.py
"""

import json
import pandas as pd
import streamlit as st

from database_layer.mongodb import check_mongo_health, query_audit_logs
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
        COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered,
        COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
    FROM audit_outbox;
    """
)
o1, o2, o3 = st.columns(3)
with o1:
    st.metric("PostgreSQL Outbox Pending", outbox_status["pending"] or 0)
with o2:
    st.metric("Delivered to MongoDB", outbox_status["delivered"] or 0)
with o3:
    st.metric("Delivery Failed Retries", outbox_status["failed"] or 0)

st.divider()

# Search & Filters
st.subheader("Filter & Inspect Security Documents")
f1, f2, f3 = st.columns([1.5, 1, 1])

with f1:
    action_filter = st.selectbox(
        "Filter by Action Type",
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
    customer_id_filter = st.text_input("Filter by Customer ID (optional)", placeholder="e.g. 1")

with f3:
    limit_count = st.selectbox("Display Limit", options=[25, 50, 100], index=1)

# Build Mongo query
criteria = {}
if action_filter != "ALL":
    criteria["action"] = action_filter
if customer_id_filter.strip():
    try:
        criteria["customer_id"] = int(customer_id_filter.strip())
    except ValueError:
        pass

# Query MongoDB
logs = query_audit_logs(criteria, limit=limit_count)

if not logs:
    st.info("No audit logs found matching the specified filters.")
else:
    st.write(f"Displaying **{len(logs)}** security audit document(s):")

    for i, log in enumerate(logs):
        ts_str = log.get("timestamp", "")
        if hasattr(ts_str, "strftime"):
            ts_str = ts_str.strftime("%Y-%m-%d %H:%M:%S")

        with st.expander(f"[{ts_str}] {log.get('action', 'LOG')} – Event ID: {log.get('event_id', 'N/A')}"):
            st.json(log)

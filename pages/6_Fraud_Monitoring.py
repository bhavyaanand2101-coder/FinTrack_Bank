"""
FinTrack - Smart Digital Banking & Loan Management System
Fraud & Compliance Monitoring Console
File: pages/6_Fraud_Monitoring.py
"""

from decimal import Decimal
import pandas as pd
import streamlit as st

from services.fraud_service import fraud_service
from ui_components import inject_custom_styles, render_sidebar, require_auth

st.set_page_config(page_title="Fraud Monitoring – FinTrack", page_icon="🚨", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="ADMIN")

st.title("🚨 Fraud & Compliance Monitoring Console")
st.caption(f"Security Compliance Officer: **{user.username}** (Admin User #{user.user_id})")

tab_open, tab_history = st.tabs(["⚠️ Open Suspicious Transfers", "📋 Historical Fraud Reviews"])

with tab_open:
    open_alerts = fraud_service.get_fraud_alerts(status_filter="OPEN")
    if not open_alerts:
        st.success("✅ No open fraud alerts or flagged transfers requiring review.")
    else:
        st.warning(f"⚠️ **{len(open_alerts)} flagged transfer(s) currently held without money movement:**")

        for alert in open_alerts:
            with st.expander(
                f"Alert #{alert['alert_id']} – Tx #{alert['transaction_id']}: ₹{float(alert['transfer_amount']):,.2f} from {alert['customer_name']}",
                expanded=True,
            ):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Sender:** {alert['customer_name']} (Account #{alert['account_id']})")
                    st.write(f"**Receiver:** {alert['receiver_name']} (Account #{alert['receiver_account_id']})")
                    st.write(f"**Amount:** ₹{float(alert['transfer_amount']):,.2f}")
                    st.write(f"**Flagged Date:** {alert['alert_created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                with c2:
                    st.write(f"**Statistical Risk Score:** {float(alert['risk_score']):.2f}")
                    st.write(f"**Anomaly / Compliance Reason:**")
                    st.info(alert["reason"])

                admin_notes = st.text_input(
                    "Compliance Notes / Resolution Justification",
                    key=f"notes_{alert['alert_id']}",
                    placeholder="Enter notes for this regulatory audit record...",
                )

                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    if st.button(f"✅ Approve & Release Funds (Tx #{alert['transaction_id']})", key=f"app_f_{alert['alert_id']}", type="primary"):
                        with st.spinner("Re-validating constraints & atomically moving funds..."):
                            try:
                                res = fraud_service.review_flagged_transfer(
                                    alert_id=alert["alert_id"],
                                    admin_user_id=user.user_id,
                                    decision="APPROVE",
                                    admin_notes=admin_notes,
                                )
                                st.success(res["message"])
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Approval Failed: {ex}")

                with col_a2:
                    if st.button(f"❌ Reject Transfer (Tx #{alert['transaction_id']})", key=f"rej_f_{alert['alert_id']}", type="secondary"):
                        with st.spinner("Rejecting transaction and retaining audit trail..."):
                            try:
                                res = fraud_service.review_flagged_transfer(
                                    alert_id=alert["alert_id"],
                                    admin_user_id=user.user_id,
                                    decision="REJECT",
                                    admin_notes=admin_notes,
                                )
                                st.warning(res["message"])
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Rejection Failed: {ex}")

with tab_history:
    st.subheader("Historical Fraud Alert Decisions")
    all_alerts = fraud_service.get_fraud_alerts()
    if all_alerts:
        df_fa = pd.DataFrame(all_alerts)
        df_fa_disp = pd.DataFrame({
            "Alert ID": df_fa["alert_id"],
            "Tx ID": df_fa["transaction_id"],
            "Sender": df_fa["customer_name"],
            "Recipient": df_fa["receiver_name"],
            "Amount": df_fa["transfer_amount"].apply(lambda v: f"₹{float(v):,.2f}"),
            "Risk Score": df_fa["risk_score"].apply(lambda v: f"{float(v):.2f}"),
            "Alert Status": df_fa["alert_status"],
            "Tx Status": df_fa["transaction_status"],
            "Created At": pd.to_datetime(df_fa["alert_created_at"]).dt.strftime("%Y-%m-%d %H:%M"),
            "Reviewed At": pd.to_datetime(df_fa["alert_reviewed_at"]).dt.strftime("%Y-%m-%d %H:%M").fillna("Pending"),
        })
        st.dataframe(df_fa_disp, use_container_width=True, hide_index=True)


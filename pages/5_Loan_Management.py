"""
FinTrack - Smart Digital Banking & Loan Management System
Administrator Loan Approval & Credit Review Portal
File: pages/5_Loan_Management.py
"""

from decimal import Decimal
import pandas as pd
import streamlit as st

from services.loan_service import loan_service
from ui_components import inject_custom_styles, render_sidebar, require_auth

st.set_page_config(page_title="Loan Management – FinTrack", page_icon="📑", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="ADMIN")

st.title("📑 Loan Application Review & Decisions")
st.caption(f"Review officer: **{user.username}** (Admin User ID: #{user.user_id})")

tab_pending, tab_all = st.tabs(["⏳ Pending Approvals", "📜 Historical Decisions"])

with tab_pending:
    pending_loans = loan_service.get_all_loans(status_filter="PENDING")
    if not pending_loans:
        st.success("🎉 No pending loan applications requiring review!")
    else:
        st.write(f"**{len(pending_loans)} application(s) awaiting administrative review:**")

        for loan in pending_loans:
            with st.expander(f"Loan #{loan['loan_id']} – {loan['customer_name']} (Requested: ₹{float(loan['requested_amount']):,.2f})", expanded=True):
                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1:
                    st.write(f"**Customer:** {loan['customer_name']}")
                    st.write(f"**Email:** {loan['customer_email']}")
                    st.write(f"**Application Date:** {loan['applied_at'].strftime('%Y-%m-%d %H:%M')}")
                with col_d2:
                    st.write(f"**Annual Income:** ₹{float(loan['annual_income']):,.2f}")
                    st.write(f"**Requested Loan:** ₹{float(loan['requested_amount']):,.2f}")
                    st.write(f"**Credit Score:** {loan['credit_score']}")
                with col_d3:
                    st.write(f"**Offered Interest Rate:** {float(loan['interest_rate']):.2f}%")
                    max_allowed = float(loan['annual_income']) * 0.50
                    st.write(f"**Max Eligible (50% Income):** ₹{max_allowed:,.2f}")
                    is_under_limit = float(loan['requested_amount']) <= max_allowed
                    st.write(f"**Debt-to-Income Check:** {'✅ Valid' if is_under_limit else '❌ Exceeds 50% limit'}")

                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    if st.button(f"✅ Approve Loan #{loan['loan_id']}", key=f"app_{loan['loan_id']}", type="primary"):
                        try:
                            res = loan_service.review_loan(
                                loan_id=loan["loan_id"],
                                admin_user_id=user.user_id,
                                decision="APPROVED",
                            )
                            st.success(res["message"])
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Approval Failed: {ex}")
                with col_btn2:
                    if st.button(f"❌ Reject Loan #{loan['loan_id']}", key=f"rej_{loan['loan_id']}", type="secondary"):
                        try:
                            res = loan_service.review_loan(
                                loan_id=loan["loan_id"],
                                admin_user_id=user.user_id,
                                decision="REJECTED",
                            )
                            st.warning(res["message"])
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Rejection Failed: {ex}")

with tab_all:
    st.subheader("All Historical Loan Applications")
    all_loans = loan_service.get_all_loans()
    if all_loans:
        df_all = pd.DataFrame(all_loans)
        df_all_disp = pd.DataFrame({
            "Loan ID": df_all["loan_id"],
            "Customer": df_all["customer_name"],
            "Requested": df_all["requested_amount"].apply(lambda v: f"₹{float(v):,.2f}"),
            "Income": df_all["annual_income"].apply(lambda v: f"₹{float(v):,.2f}"),
            "Credit Score": df_all["credit_score"],
            "Interest Rate": df_all["interest_rate"].apply(lambda v: f"{float(v):.2f}%"),
            "Status": df_all["status"],
            "Applied Date": pd.to_datetime(df_all["applied_at"]).dt.strftime("%Y-%m-%d"),
            "Reviewed By": df_all["reviewer_username"].fillna("—"),
        })
        st.dataframe(df_all_disp, use_container_width=True, hide_index=True)


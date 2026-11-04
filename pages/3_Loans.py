"""
FinTrack - Smart Digital Banking & Loan Management System
Loan Application Portal
File: pages/3_Loans.py
"""

from decimal import Decimal
import pandas as pd
import streamlit as st

from services.loan_service import loan_service
from ui_components import inject_custom_styles, render_sidebar, require_auth

st.set_page_config(page_title="Loan Application – FinTrack", page_icon="📝", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="CUSTOMER")

st.title("📝 Personal Loan Center")
st.caption("Apply for personal credit with instant algorithmic eligibility and documented database rules.")

col_apply, col_calc = st.columns([1.2, 1])

with col_calc:
    st.subheader("💡 Eligibility Calculator Preview")
    calc_income = st.number_input("Annual Income (INR)", min_value=10000.0, value=650000.0, step=25000.0)
    calc_amount = st.number_input("Requested Loan Amount (INR)", min_value=5000.0, value=150000.0, step=10000.0)
    calc_credit = st.slider("Credit Score (CIBIL)", min_value=300, max_value=900, value=750)

    try:
        eval_res = loan_service.calculate_eligibility(calc_income, calc_amount, calc_credit)
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4px solid {'#10B981' if eval_res['is_eligible'] else '#EF4444'};">
                <div class="metric-title">Eligibility Status</div>
                <div style="font-size: 20px; font-weight: 700; color: {'#059669' if eval_res['is_eligible'] else '#DC2626'};">
                    {eval_res['status']}
                </div>
                <hr style="margin: 10px 0; border: none; border-top: 1px solid #E2E8F0;"/>
                <div style="font-size: 13px; color: #475569;">
                    <div><strong>Max Eligible Amount (50% Income):</strong> ₹{float(eval_res['max_eligible_amount']):,.2f}</div>
                    <div><strong>Suggested Interest Rate:</strong> {float(eval_res['suggested_interest_rate']):.2f}% p.a.</div>
                    <div><strong>Eligibility Assessment:</strong> {'Qualified for application review' if eval_res['is_eligible'] else 'Exceeds debt-to-income or minimum credit guidelines'}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as ex:
        st.error(f"Calculator Error: {ex}")

with col_apply:
    st.subheader("Submit Loan Application")
    with st.form("loan_application_form"):
        st.write("Confirm details below to submit your official application:")
        income_field = st.number_input("Confirmed Annual Income (INR)", min_value=10000.0, value=float(calc_income), step=25000.0)
        amount_field = st.number_input("Confirmed Loan Amount (INR)", min_value=5000.0, value=float(calc_amount), step=10000.0)
        credit_field = st.number_input("Credit Score", min_value=300, max_value=900, value=int(calc_credit))

        submit_loan = st.form_submit_button("Submit Application", type="primary", use_container_width=True)

        if submit_loan:
            try:
                res = loan_service.apply_for_loan(
                    customer_id=user.customer_id,
                    requested_amount=Decimal(str(amount_field)),
                    annual_income=Decimal(str(income_field)),
                    credit_score=int(credit_field),
                )
                st.success(f"🎉 {res['message']} (Application ID: #{res['loan_id']})")
                st.rerun()
            except Exception as e:
                st.error(f"Application Submission Failed: {e}")

st.divider()

# Customer's loan history
st.subheader("Your Loan Application History")
my_loans = loan_service.get_customer_loans(user.customer_id)
if not my_loans:
    st.info("You have not submitted any loan applications yet.")
else:
    df_loans = pd.DataFrame(my_loans)
    df_disp = pd.DataFrame({
        "Application ID": df_loans["loan_id"],
        "Applied Date": pd.to_datetime(df_loans["applied_at"]).dt.strftime("%Y-%m-%d %H:%M"),
        "Requested Amount": df_loans["requested_amount"].apply(lambda v: f"₹{float(v):,.2f}"),
        "Annual Income": df_loans["annual_income"].apply(lambda v: f"₹{float(v):,.2f}"),
        "Credit Score": df_loans["credit_score"],
        "Interest Rate": df_loans["interest_rate"].apply(lambda v: f"{float(v):.2f}%"),
        "Status": df_loans["status"],
        "Reviewed At": pd.to_datetime(df_loans["reviewed_at"]).dt.strftime("%Y-%m-%d %H:%M").fillna("Pending"),
        "Reviewer": df_loans["reviewer_username"].fillna("Awaiting review"),
    })
    st.dataframe(df_disp, use_container_width=True, hide_index=True)


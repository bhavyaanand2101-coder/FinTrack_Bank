"""
FinTrack - Smart Digital Banking & Loan Management System
Fund Transfer Interface
File: pages/2_Transfers.py
"""

from decimal import Decimal
import uuid
import streamlit as st

from database_layer.postgres import DatabaseError, fetch_one
from services.account_service import account_service
from services.transfer_service import transfer_service
from ui_components import inject_custom_styles, render_sidebar, require_auth

st.set_page_config(page_title="Fund Transfer – FinTrack", page_icon="💸", layout="wide")
inject_custom_styles()
render_sidebar()
user = require_auth(role="CUSTOMER")

st.title("💸 Immediate Fund Transfer")
st.caption("Execute instant transfers protected by ACID transactions, deterministic row-locking, and ML fraud anomaly detection.")

# Fetch user accounts
accounts = account_service.get_customer_accounts(user.customer_id)
if not accounts:
    st.error("No accounts found for your customer ID.")
    st.stop()

# Initialize unique idempotency key for this form session
if "transfer_idempotency_key" not in st.session_state:
    st.session_state["transfer_idempotency_key"] = str(uuid.uuid4())

col_transfer, col_info = st.columns([1.3, 1])

with col_transfer:
    sender_options = {
        f"#{acc['account_id']} – {acc['account_type']} (Available: ₹{acc['balance']:,.2f})": acc["account_id"]
        for acc in accounts
    }
    selected_sender_label = st.selectbox("From Account", options=list(sender_options.keys()))
    sender_account_id = sender_options[selected_sender_label]
    sender_acc = account_service.get_account_by_id(sender_account_id, customer_id=user.customer_id)

    receiver_account_input = st.number_input(
        "To Account Number (Receiver Account ID)",
        min_value=1,
        value=1003,
        step=1,
        help="Enter the destination account ID (e.g., 1003 for Priya Sharma).",
    )

    # Live receiver verification
    receiver_acc = fetch_one(
        """
        SELECT a.account_id, a.customer_id, c.full_name, a.currency, a.is_frozen
        FROM accounts a
        JOIN customers c ON a.customer_id = c.customer_id
        WHERE a.account_id = %s;
        """,
        (receiver_account_input,),
    )

    if receiver_acc:
        if receiver_acc["account_id"] == sender_account_id:
            st.warning("⚠️ Receiver account cannot be the same as the sender account.")
        elif receiver_acc["is_frozen"]:
            st.error("⚠️ Receiver account is currently FROZEN and cannot accept funds.")
        else:
            st.info(f"Verified Recipient: **{receiver_acc['full_name']}** (Account #{receiver_acc['account_id']})")
    else:
        st.warning(f"⚠️ Account #{receiver_account_input} not found in the banking registry.")

    amount_input = st.number_input(
        "Transfer Amount (INR)",
        min_value=1.0,
        max_value=float(sender_acc["balance"]) if sender_acc["balance"] > 0 else 1000000.0,
        value=1500.0,
        step=100.0,
    )

    description_input = st.text_input("Transfer Description", value="Invoice settlement / Personal transfer")

    # Real-time fraud detection warning
    if amount_input >= 10000.0:
        st.warning(
            "⚠️ **Compliance Notice:** Transfers of INR 10,000.00 or greater require mandatory fraud compliance review. "
            "Money will NOT be debited until approved by bank administration."
        )

    st.markdown(f"**Transaction Reference (Idempotency Key):** `{st.session_state['transfer_idempotency_key']}`")

    submit_transfer = st.button("Authorize & Transfer Funds", type="primary", use_container_width=True)

    if submit_transfer:
        if receiver_account_input == sender_account_id:
            st.error("Cannot transfer funds to the same account.")
        elif not receiver_acc:
            st.error(f"Receiver account #{receiver_account_input} does not exist.")
        elif sender_acc["balance"] < Decimal(str(amount_input)):
            st.error("Insufficient funds in selected sender account.")
        else:
            with st.spinner("Processing transaction securely..."):
                try:
                    result = transfer_service.execute_transfer(
                        authenticated_customer_id=user.customer_id,
                        sender_account_id=sender_account_id,
                        receiver_account_id=receiver_account_input,
                        amount=Decimal(str(amount_input)),
                        description=description_input,
                        idempotency_key=st.session_state["transfer_idempotency_key"],
                    )

                    # Reset idempotency key for next transfer
                    st.session_state["transfer_idempotency_key"] = str(uuid.uuid4())

                    if result["status"] == "SUCCESS":
                        st.success(f"✅ {result['message']}")
                        st.balloons()
                        st.markdown(
                            f"""
                            <div class="metric-card" style="border-left: 4px solid #10B981;">
                                <div class="metric-title">Transfer Confirmation</div>
                                <div><strong>Transaction ID:</strong> #{result['transaction_id']}</div>
                                <div><strong>Amount:</strong> ₹{float(result['amount']):,.2f}</div>
                                <div><strong>Remaining Balance:</strong> ₹{float(result['new_balance']):,.2f}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    elif result["status"] == "FLAGGED":
                        st.warning(f"⚠️ {result['message']}")
                        st.markdown(
                            f"""
                            <div class="metric-card" style="border-left: 4px solid #F59E0B;">
                                <div class="metric-title">Compliance Review Triggered</div>
                                <div><strong>Transaction ID:</strong> #{result['transaction_id']} (Status: FLAGGED)</div>
                                <div><strong>Alert ID:</strong> #{result.get('alert_id')}</div>
                                <div><strong>Risk Score:</strong> {result.get('risk_score', 0.0):.2f}</div>
                                <div><strong>Reason:</strong> {result.get('reason')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info(f"Transaction Status: {result['status']} – {result.get('message')}")

                except Exception as ex:
                    st.error(f"Transaction Execution Failed: {ex}")

with col_info:
    st.markdown(
        """
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 20px; border-radius: 8px;">
            <h4 style="margin-top:0; color: #0F172A;">Transaction Engine Architecture</h4>
            <ul style="font-size: 13px; color: #475569; padding-left: 20px; line-height: 1.6;">
                <li><strong>ACID Isolation:</strong> Row-level locks acquired with <code>SELECT ... FOR UPDATE</code>.</li>
                <li><strong>Ascending Lock Ordering:</strong> Always locks <code>account_id</code> in ascending order to mathematically prevent deadlocks.</li>
                <li><strong>Idempotency:</strong> Prevents duplicate debits from network retries or double-clicks.</li>
                <li><strong>Double-Entry Ledger:</strong> Every success generates balanced debit and credit entries.</li>
                <li><strong>ML Anomaly Detection:</strong> Statistical Z-score evaluates deviations against personal history.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


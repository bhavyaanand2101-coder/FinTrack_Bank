import React, { useEffect, useState } from 'react';
import { accountsAPI, transfersAPI } from '../../api/client';
import ConfirmationModal from '../../components/ConfirmationModal';
import StatusBadge from '../../components/StatusBadge';
import Alert from '../../components/Alert';
import {
  ArrowLeftRight,
  ShieldAlert,
  CheckCircle2,
  Clock,
  UserCheck,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';

const TransferMoney = () => {
  const [accounts, setAccounts] = useState([]);
  const [senderAccountId, setSenderAccountId] = useState('');
  const [receiverAccountNumber, setReceiverAccountNumber] = useState('');
  const [recipientInfo, setRecipientInfo] = useState(null);
  const [recipientError, setRecipientError] = useState('');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('Immediate Fund Transfer');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [transferReceipt, setTransferReceipt] = useState(null);

  useEffect(() => {
    accountsAPI
      .getAccounts()
      .then((res) => {
        setAccounts(res.data);
        if (res.data.length > 0) {
          setSenderAccountId(res.data[0].account_id);
        }
      })
      .catch(() => setError('Failed to load accounts.'));
  }, []);

  // Live lookup of recipient account
  const handleRecipientLookup = async (accNum) => {
    setReceiverAccountNumber(accNum);
    setRecipientInfo(null);
    setRecipientError('');

    if (!accNum || isNaN(accNum) || accNum.length < 3) return;

    try {
      const res = await transfersAPI.lookupRecipient(Number(accNum));
      setRecipientInfo(res.data);
    } catch (err) {
      setRecipientError(err.response?.data?.detail || 'Account not found.');
    }
  };

  const selectedAccount = accounts.find((a) => a.account_id === Number(senderAccountId));
  const transferAmount = parseFloat(amount || 0);
  const isHighValue = transferAmount >= 10000;

  const handlePreSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!senderAccountId) {
      setError('Please select a funding account.');
      return;
    }
    if (!receiverAccountNumber || !recipientInfo) {
      setError('Please verify a valid recipient account.');
      return;
    }
    if (Number(senderAccountId) === Number(receiverAccountNumber)) {
      setError('Sender and receiver accounts must be different.');
      return;
    }
    if (isNaN(transferAmount) || transferAmount <= 0) {
      setError('Transfer amount must be strictly positive.');
      return;
    }
    if (selectedAccount && transferAmount > parseFloat(selectedAccount.balance)) {
      setError(`Insufficient balance. Available: ₹${parseFloat(selectedAccount.balance).toLocaleString('en-IN')}`);
      return;
    }

    setIsModalOpen(true);
  };

  const handleExecuteTransfer = async () => {
    setIsModalOpen(false);
    setLoading(true);
    setError('');
    setTransferReceipt(null);

    try {
      const idempotencyKey = crypto.randomUUID();
      const res = await transfersAPI.executeTransfer({
        sender_account_id: Number(senderAccountId),
        receiver_account_id: Number(receiverAccountNumber),
        amount: transferAmount,
        description,
        idempotency_key: idempotencyKey,
      });

      setTransferReceipt({
        ...res.data,
        timestamp: new Date().toISOString(),
        senderAccount: senderAccountId,
        receiverAccount: receiverAccountNumber,
        receiverName: recipientInfo.customer_name,
      });

      // Refresh accounts balance
      const updatedAccounts = await accountsAPI.getAccounts();
      setAccounts(updatedAccounts.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Transfer processing failed. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setTransferReceipt(null);
    setAmount('');
    setReceiverAccountNumber('');
    setRecipientInfo(null);
    setDescription('Immediate Fund Transfer');
    setError('');
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Fund Transfer Center</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Atomic database transactions protected by deterministic row locking and double-entry ledger records.
        </p>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {/* Transfer Receipt Card */}
      {transferReceipt ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 card-shadow text-center space-y-6">
          <div className="w-16 h-16 mx-auto rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
            {transferReceipt.status === 'SUCCESS' ? (
              <CheckCircle2 className="w-8 h-8" />
            ) : (
              <Clock className="w-8 h-8 text-amber-500" />
            )}
          </div>

          <div>
            <span className="text-xs uppercase font-bold text-slate-400">Transfer Confirmation</span>
            <h2 className="text-3xl font-extrabold text-slate-900 mt-1">
              ₹{parseFloat(transferReceipt.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </h2>
            <div className="mt-2">
              <StatusBadge status={transferReceipt.status} />
            </div>
            <p className="text-xs text-slate-600 mt-3 max-w-md mx-auto">{transferReceipt.message}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 max-w-md mx-auto text-left text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-500">Transaction ID:</span>
              <span className="font-mono font-bold text-slate-800">#{transferReceipt.transaction_id || 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">From Account:</span>
              <span className="font-semibold text-slate-800">#{transferReceipt.senderAccount}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">To Beneficiary:</span>
              <span className="font-semibold text-slate-800">
                {transferReceipt.receiverName} (#{transferReceipt.receiverAccount})
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Timestamp:</span>
              <span className="text-slate-700">{new Date(transferReceipt.timestamp).toLocaleString()}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center space-x-2 px-6 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-bold rounded-xl transition shadow-md"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Make Another Transfer</span>
          </button>
        </div>
      ) : (
        /* Transfer Input Form */
        <div className="bg-white rounded-2xl border border-slate-200 p-8 card-shadow">
          <form onSubmit={handlePreSubmit} className="space-y-6">
            {/* Funding Account Selection */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Funding Account (Debit Source)
              </label>
              <select
                value={senderAccountId}
                onChange={(e) => setSenderAccountId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-accent"
                required
              >
                {accounts.map((acc) => (
                  <option key={acc.account_id} value={acc.account_id}>
                    #{acc.account_id} – {acc.account_type} (Available: ₹
                    {parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })})
                  </option>
                ))}
              </select>
            </div>

            {/* Recipient Account Number */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Beneficiary Account Number
              </label>
              <input
                type="number"
                value={receiverAccountNumber}
                onChange={(e) => handleRecipientLookup(e.target.value)}
                placeholder="Enter recipient account ID (e.g. 1003)"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                required
              />

              {/* Recipient Lookup Result Card */}
              {recipientInfo && (
                <div className="mt-2 p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800">
                  <div className="flex items-center space-x-2">
                    <UserCheck className="w-4 h-4 text-emerald-600" />
                    <span>
                      Beneficiary: <strong>{recipientInfo.customer_name}</strong> ({recipientInfo.account_type})
                    </span>
                  </div>
                  <span className="font-semibold text-emerald-700">Verified</span>
                </div>
              )}
              {recipientError && (
                <p className="mt-1.5 text-xs text-rose-600 font-medium">{recipientError}</p>
              )}
            </div>

            {/* Amount */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Transfer Amount (INR)
              </label>
              <div className="relative">
                <span className="absolute left-4 top-2.5 text-slate-400 font-bold text-base">₹</span>
                <input
                  type="number"
                  step="0.01"
                  min="1.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-lg font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-accent"
                  required
                />
              </div>

              {/* High value threshold notice */}
              {isHighValue && (
                <div className="mt-2.5 p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start space-x-2 text-xs text-amber-800">
                  <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Fraud Review Threshold Notice:</span>
                    <p className="mt-0.5 text-amber-700">
                      Transfers $\ge$ ₹10,000 are placed on compliance hold as <strong>FLAGGED</strong>.
                      Zero funds will be deducted from your account until approved by a bank officer.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Transfer Remarks / Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={200}
                placeholder="e.g. Rent payment or Invoice #482"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !recipientInfo}
              className="w-full py-3 px-4 bg-accent hover:bg-accent-hover text-white text-sm font-bold rounded-xl transition shadow-md flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <ArrowLeftRight className="w-4 h-4" />
              <span>{loading ? 'Processing Transaction...' : 'Review & Confirm Transfer'}</span>
            </button>
          </form>
        </div>
      )}

      {/* Pre-Authorization Confirmation Modal */}
      <ConfirmationModal
        isOpen={isModalOpen}
        title="Confirm Fund Transfer"
        message={`Are you sure you want to transfer ₹${transferAmount.toLocaleString('en-IN', {
          minimumFractionDigits: 2,
        })} from Account #${senderAccountId} to ${recipientInfo?.customer_name} (#${receiverAccountNumber})?`}
        confirmText="Execute Transfer"
        confirmVariant="primary"
        onConfirm={handleExecuteTransfer}
        onClose={() => setIsModalOpen(false)}
      >
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-1">
          <p>• Sender Account: <strong>#{senderAccountId}</strong></p>
          <p>• Recipient: <strong>{recipientInfo?.customer_name} (#{receiverAccountNumber})</strong></p>
          <p>• Amount: <strong>₹{transferAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></p>
          <p>• Description: <em>{description}</em></p>
        </div>
      </ConfirmationModal>
    </div>
  );
};

export default TransferMoney;


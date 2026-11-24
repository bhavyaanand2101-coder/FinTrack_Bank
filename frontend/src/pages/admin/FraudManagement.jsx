import React, { useEffect, useState } from 'react';
import { fraudAPI } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import ConfirmationModal from '../../components/ConfirmationModal';
import Alert from '../../components/Alert';
import { ShieldAlert, CheckCircle2, XCircle, ArrowRight, ShieldCheck } from 'lucide-react';

const FraudManagement = () => {
  const [alerts, setAlerts] = useState([]);
  const [activeTab, setActiveTab] = useState('OPEN'); // 'OPEN' | 'HISTORY'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Modal state
  const [modalState, setModalState] = useState({
    isOpen: false,
    alertId: null,
    decision: 'APPROVE', // 'APPROVE' | 'REJECT'
    amount: '0',
    sender: '',
    receiver: '',
  });

  useEffect(() => {
    loadAlerts();
  }, [activeTab]);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const res = await fraudAPI.getFraudAlerts(activeTab === 'OPEN' ? 'OPEN' : null);
      setAlerts(res.data);
    } catch (err) {
      setError('Failed to fetch fraud alerts.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDecision = (alertId, decision, amount, sender, receiver) => {
    setModalState({
      isOpen: true,
      alertId,
      decision,
      amount,
      sender,
      receiver,
    });
  };

  const handleConfirmDecision = async () => {
    const { alertId, decision } = modalState;
    setModalState({ ...modalState, isOpen: false });

    try {
      if (decision === 'APPROVE') {
        const res = await fraudAPI.approveFraudAlert(alertId, 'Approved by compliance administrator.');
        setSuccess(res.data.message);
      } else {
        const res = await fraudAPI.rejectFraudAlert(alertId, 'Rejected by compliance administrator.');
        setSuccess(res.data.message);
      }
      loadAlerts();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to execute fraud decision.');
    }
  };

  const filteredAlerts = activeTab === 'OPEN'
    ? alerts.filter((a) => a.alert_status === 'OPEN')
    : alerts.filter((a) => a.alert_status !== 'OPEN');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Fraud Review & Flagged Holds</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Deterministic rule-flagged transfers held pending compliance verification
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('OPEN')}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition ${
              activeTab === 'OPEN' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Open Alerts ({alerts.filter((a) => a.alert_status === 'OPEN').length})
          </button>
          <button
            onClick={() => setActiveTab('HISTORY')}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition ${
              activeTab === 'HISTORY' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Review History
          </button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {/* Flagged Transfers List */}
      <div className="space-y-4">
        {loading ? (
          <div className="text-center py-12 text-xs text-slate-400">Loading compliance alerts...</div>
        ) : filteredAlerts.length > 0 ? (
          filteredAlerts.map((alert) => (
            <div
              key={alert.alert_id}
              className="bg-white rounded-2xl border border-slate-200 p-6 card-shadow space-y-4"
            >
              {/* Alert Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-100 gap-2">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold text-sm">
                    <ShieldAlert className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      Alert #{alert.alert_id} – Transaction #{alert.transaction_id}
                    </h3>
                    <p className="text-xs text-slate-500">
                      Originating Account: #{alert.account_id}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <StatusBadge status={alert.alert_status} />
                  <span className="text-xs text-slate-400">
                    Flagged: {new Date(alert.alert_created_at).toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Transaction Metrics */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">Hold Amount</span>
                  <p className="text-base font-extrabold text-slate-900 mt-0.5">
                    ₹{parseFloat(alert.amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </p>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">Sender Customer</span>
                  <p className="text-base font-bold text-slate-800 mt-0.5">
                    {alert.sender_name || `Account #${alert.account_id}`}
                  </p>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">Intended Recipient</span>
                  <p className="text-base font-bold text-slate-800 mt-0.5">{alert.receiver_name || 'N/A'}</p>
                </div>
              </div>

              {/* Reason Box */}
              <div className="p-3 bg-amber-50/50 border border-amber-200/60 rounded-xl text-xs text-amber-900">
                <span className="font-bold">Flagged Reason:</span> {alert.reason}
              </div>

              {/* Actions for OPEN alerts */}
              {alert.alert_status === 'OPEN' && (
                <div className="pt-2 flex items-center justify-end space-x-3">
                  <button
                    onClick={() =>
                      handleOpenDecision(
                        alert.alert_id,
                        'REJECT',
                        alert.amount,
                        alert.sender_name,
                        alert.receiver_name
                      )
                    }
                    className="px-4 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold rounded-xl transition flex items-center space-x-1.5"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>Reject & Void (0 Movement)</span>
                  </button>

                  <button
                    onClick={() =>
                      handleOpenDecision(
                        alert.alert_id,
                        'APPROVE',
                        alert.amount,
                        alert.sender_name,
                        alert.receiver_name
                      )
                    }
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition shadow-sm flex items-center space-x-1.5"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Approve & Release Funds</span>
                  </button>
                </div>
              )}

              {/* Historical info */}
              {alert.alert_status !== 'OPEN' && (
                <div className="pt-2 text-xs text-slate-500 flex items-center justify-between border-t border-slate-50">
                  <span>Resolution: <strong>{alert.alert_status}</strong></span>
                  <span>Reviewed: {alert.reviewed_at ? new Date(alert.reviewed_at).toLocaleString() : 'N/A'}</span>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-xs text-slate-400">
            No compliance alerts found in this section.
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={modalState.isOpen}
        title={
          modalState.decision === 'APPROVE'
            ? 'Approve & Execute Flagged Transfer'
            : 'Reject & Void Flagged Transfer'
        }
        message={
          modalState.decision === 'APPROVE'
            ? `Approving Alert #${modalState.alertId} will atomically re-lock both accounts, debit ₹${parseFloat(
                modalState.amount
              ).toLocaleString('en-IN')} from ${modalState.sender}, credit ${
                modalState.receiver
              }, and record balanced ledger entries. Proceed?`
            : `Rejecting Alert #${modalState.alertId} will mark the transaction FAILED. No money will be moved. Proceed?`
        }
        confirmText={modalState.decision === 'APPROVE' ? 'Execute Release' : 'Void Transfer'}
        confirmVariant={modalState.decision === 'APPROVE' ? 'primary' : 'danger'}
        onConfirm={handleConfirmDecision}
        onClose={() => setModalState({ ...modalState, isOpen: false })}
      />
    </div>
  );
};

export default FraudManagement;


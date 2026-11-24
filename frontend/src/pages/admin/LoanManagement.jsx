import React, { useEffect, useState } from 'react';
import { loansAPI } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import ConfirmationModal from '../../components/ConfirmationModal';
import Alert from '../../components/Alert';
import { CheckSquare, XCircle, CheckCircle2, Clock, UserCheck } from 'lucide-react';

const LoanManagement = () => {
  const [loans, setLoans] = useState([]);
  const [activeTab, setActiveTab] = useState('PENDING'); // 'PENDING' | 'HISTORY'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Decision Modal State
  const [modalState, setModalState] = useState({
    isOpen: false,
    loanId: null,
    decision: 'APPROVE', // 'APPROVE' | 'REJECT'
    applicantName: '',
    amount: '0',
  });

  useEffect(() => {
    loadLoans();
  }, [activeTab]);

  const loadLoans = async () => {
    try {
      setLoading(true);
      const res = await loansAPI.getAdminLoans(activeTab === 'PENDING' ? 'PENDING' : null);
      setLoans(res.data);
    } catch (err) {
      setError('Failed to fetch loan applications.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDecision = (loanId, decision, applicantName, amount) => {
    setModalState({
      isOpen: true,
      loanId,
      decision,
      applicantName,
      amount,
    });
  };

  const handleConfirmDecision = async () => {
    const { loanId, decision } = modalState;
    setModalState({ ...modalState, isOpen: false });

    try {
      if (decision === 'APPROVE') {
        const res = await loansAPI.approveLoan(loanId);
        setSuccess(res.data.message);
      } else {
        const res = await loansAPI.rejectLoan(loanId);
        setSuccess(res.data.message);
      }
      loadLoans();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process loan decision.');
    }
  };

  const filteredLoans = activeTab === 'PENDING'
    ? loans.filter((l) => l.status === 'PENDING')
    : loans.filter((l) => l.status !== 'PENDING');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Loan Applications & Credit Review</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluate debt-to-income limits and approve or reject applicant loan requests
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('PENDING')}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition ${
              activeTab === 'PENDING' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Pending Reviews
          </button>
          <button
            onClick={() => setActiveTab('HISTORY')}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition ${
              activeTab === 'HISTORY' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Decision History
          </button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {/* Loan Applications List */}
      <div className="space-y-4">
        {loading ? (
          <div className="text-center py-12 text-xs text-slate-400">Loading loan records...</div>
        ) : filteredLoans.length > 0 ? (
          filteredLoans.map((loan) => (
            <div
              key={loan.loan_id}
              className="bg-white rounded-2xl border border-slate-200 p-6 card-shadow space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-100 gap-2">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 text-accent flex items-center justify-center font-bold text-sm">
                    #{loan.loan_id}
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">{loan.customer_name}</h3>
                    <p className="text-xs text-slate-500">
                      Customer #{loan.customer_id} • Email: {loan.customer_email}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <StatusBadge status={loan.status} />
                  <span className="text-xs text-slate-400">
                    Applied: {new Date(loan.applied_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Loan Details Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">Requested Amount</span>
                  <p className="text-base font-extrabold text-slate-900 mt-0.5">
                    ₹{parseFloat(loan.requested_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </p>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">Annual Income</span>
                  <p className="text-base font-bold text-slate-800 mt-0.5">
                    ₹{parseFloat(loan.annual_income).toLocaleString('en-IN')}
                  </p>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">CIBIL Credit Score</span>
                  <p
                    className={`text-base font-bold mt-0.5 ${
                      loan.credit_score >= 750
                        ? 'text-emerald-600'
                        : loan.credit_score >= 650
                        ? 'text-blue-600'
                        : 'text-rose-600'
                    }`}
                  >
                    {loan.credit_score}
                  </p>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl">
                  <span className="text-slate-400 font-semibold uppercase">Interest Rate</span>
                  <p className="text-base font-bold text-slate-800 mt-0.5">{loan.interest_rate}% p.a.</p>
                </div>
              </div>

              {/* Action Buttons for Pending Loans */}
              {loan.status === 'PENDING' && (
                <div className="pt-2 flex items-center justify-end space-x-3">
                  <button
                    onClick={() => handleOpenDecision(loan.loan_id, 'REJECT', loan.customer_name, loan.requested_amount)}
                    className="px-4 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold rounded-xl transition flex items-center space-x-1.5"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>Reject Application</span>
                  </button>

                  <button
                    onClick={() => handleOpenDecision(loan.loan_id, 'APPROVE', loan.customer_name, loan.requested_amount)}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition shadow-sm flex items-center space-x-1.5"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Approve Loan</span>
                  </button>
                </div>
              )}

              {/* Historical decision info */}
              {loan.status !== 'PENDING' && (
                <div className="pt-2 text-xs text-slate-500 flex items-center justify-between border-t border-slate-50">
                  <span>Reviewed By: <strong>@{loan.reviewer_username || 'admin'}</strong></span>
                  <span>Decision Date: {loan.reviewed_at ? new Date(loan.reviewed_at).toLocaleString() : 'N/A'}</span>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-xs text-slate-400">
            No loan applications found in this category.
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={modalState.isOpen}
        title={modalState.decision === 'APPROVE' ? 'Approve Loan Application' : 'Reject Loan Application'}
        message={
          modalState.decision === 'APPROVE'
            ? `Are you sure you want to approve Loan #${modalState.loanId} for ${modalState.applicantName} for ₹${parseFloat(
                modalState.amount
              ).toLocaleString('en-IN')}?`
            : `Are you sure you want to reject Loan #${modalState.loanId} for ${modalState.applicantName}?`
        }
        confirmText={modalState.decision === 'APPROVE' ? 'Confirm Approval' : 'Confirm Rejection'}
        confirmVariant={modalState.decision === 'APPROVE' ? 'primary' : 'danger'}
        onConfirm={handleConfirmDecision}
        onClose={() => setModalState({ ...modalState, isOpen: false })}
      />
    </div>
  );
};

export default LoanManagement;


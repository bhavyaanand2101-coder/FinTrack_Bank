import React, { useEffect, useState } from 'react';
import { loansAPI } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import Alert from '../../components/Alert';
import { FileText, Calculator, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react';

const Loans = () => {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Eligibility Calculator state
  const [calcData, setCalcData] = useState({
    annual_income: '600000',
    requested_amount: '150000',
    credit_score: '750',
  });
  const [calcResult, setCalcResult] = useState(null);
  const [calcLoading, setCalcLoading] = useState(false);

  // Application form state
  const [applyData, setApplyData] = useState({
    annual_income: '600000',
    requested_amount: '150000',
    credit_score: '750',
  });
  const [applyLoading, setApplyLoading] = useState(false);

  useEffect(() => {
    loadCustomerLoans();
    handleCalculatePreview();
  }, []);

  const loadCustomerLoans = async () => {
    try {
      setLoading(true);
      const res = await loansAPI.getCustomerLoans();
      setLoans(res.data);
    } catch (err) {
      setError('Failed to fetch your loan history.');
    } finally {
      setLoading(false);
    }
  };

  const handleCalculatePreview = async () => {
    try {
      setCalcLoading(true);
      const res = await loansAPI.calculateEligibility({
        annual_income: parseFloat(calcData.annual_income),
        requested_amount: parseFloat(calcData.requested_amount),
        credit_score: parseInt(calcData.credit_score, 10),
      });
      setCalcResult(res.data);
    } catch (err) {
      setCalcResult(null);
    } finally {
      setCalcLoading(false);
    }
  };

  const handleApply = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setApplyLoading(true);

    try {
      const res = await loansAPI.applyForLoan({
        annual_income: parseFloat(applyData.annual_income),
        requested_amount: parseFloat(applyData.requested_amount),
        credit_score: parseInt(applyData.credit_score, 10),
      });
      setSuccess(`Loan application #${res.data.loan_id} successfully submitted and queued for administrator review!`);
      loadCustomerLoans();
    } catch (err) {
      setError(err.response?.data?.detail || 'Loan application failed.');
    } finally {
      setApplyLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Personal Loans & Credit Center</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Deterministic fixed-rule loan assessment matching database view <code className="bg-slate-100 px-1 py-0.5 rounded">View_Loan_Eligibility</code>
        </p>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Instant Eligibility Calculator Preview */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow space-y-4">
          <div className="flex items-center space-x-2 text-accent">
            <Calculator className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">Eligibility Calculator Preview</h3>
          </div>
          <p className="text-xs text-slate-500">
            Rules: Max loan amount = 50% of annual income. Minimum CIBIL score = 650.
          </p>

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Annual Income (INR)</label>
              <input
                type="number"
                value={calcData.annual_income}
                onChange={(e) => setCalcData({ ...calcData, annual_income: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-sm focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Requested Loan Amount (INR)</label>
              <input
                type="number"
                value={calcData.requested_amount}
                onChange={(e) => setCalcData({ ...calcData, requested_amount: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-sm focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Credit Score: <span className="text-accent font-bold">{calcData.credit_score}</span>
              </label>
              <input
                type="range"
                min="300"
                max="900"
                step="5"
                value={calcData.credit_score}
                onChange={(e) => setCalcData({ ...calcData, credit_score: e.target.value })}
                className="w-full accent-accent"
              />
              <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                <span>300 (Poor)</span>
                <span>650 (Eligible)</span>
                <span>750+ (Prime)</span>
                <span>900 (Excellent)</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleCalculatePreview}
              disabled={calcLoading}
              className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl transition"
            >
              {calcLoading ? 'Calculating...' : 'Recalculate Eligibility'}
            </button>
          </div>

          {/* Calculator Output Card */}
          {calcResult && (
            <div
              className={`p-4 rounded-xl border ${
                calcResult.is_eligible
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-rose-50 border-rose-200 text-rose-900'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider">Evaluation Status</span>
                <StatusBadge status={calcResult.status} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-500">Max Eligible Cap:</span>
                  <p className="font-bold">
                    ₹{parseFloat(calcResult.max_eligible_amount).toLocaleString('en-IN')}
                  </p>
                </div>
                <div>
                  <span className="text-slate-500">Suggested Rate:</span>
                  <p className="font-bold">{calcResult.suggested_interest_rate}% p.a.</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Loan Application Submission Form */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow space-y-4">
          <div className="flex items-center space-x-2 text-accent">
            <FileText className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">Submit Loan Application</h3>
          </div>
          <p className="text-xs text-slate-500">
            Submit your loan request for official bank administrative approval.
          </p>

          <form onSubmit={handleApply} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Annual Income (INR)</label>
              <input
                type="number"
                value={applyData.annual_income}
                onChange={(e) => setApplyData({ ...applyData, annual_income: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-sm focus:ring-2 focus:ring-accent"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Requested Amount (INR)</label>
              <input
                type="number"
                value={applyData.requested_amount}
                onChange={(e) => setApplyData({ ...applyData, requested_amount: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-sm focus:ring-2 focus:ring-accent"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Verified Credit Score (CIBIL)</label>
              <input
                type="number"
                min="300"
                max="900"
                value={applyData.credit_score}
                onChange={(e) => setApplyData({ ...applyData, credit_score: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-sm focus:ring-2 focus:ring-accent"
                required
              />
            </div>

            <button
              type="submit"
              disabled={applyLoading}
              className="w-full py-3 bg-accent hover:bg-accent-hover text-white text-sm font-bold rounded-xl transition shadow-md flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <span>{applyLoading ? 'Submitting Application...' : 'Apply for Loan'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* Customer Loan Applications Table */}
      <div className="bg-white rounded-2xl border border-slate-200 card-shadow overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">Your Loan Application History</h3>
          <span className="text-xs text-slate-500 font-medium">{loans.length} applications</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
              <tr>
                <th className="py-3 px-4">Loan ID</th>
                <th className="py-3 px-4">Date Applied</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Annual Income</th>
                <th className="py-3 px-4">Credit Score</th>
                <th className="py-3 px-4">Rate</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Reviewer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loans.length > 0 ? (
                loans.map((loan) => (
                  <tr key={loan.loan_id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">#{loan.loan_id}</td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(loan.applied_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">
                      ₹{parseFloat(loan.requested_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      ₹{parseFloat(loan.annual_income).toLocaleString('en-IN')}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-800">{loan.credit_score}</td>
                    <td className="py-3 px-4 text-xs font-semibold text-slate-700">{loan.interest_rate}%</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={loan.status} />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {loan.reviewer_username ? `@${loan.reviewer_username}` : 'Pending Review'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-xs text-slate-400">
                    No loan applications submitted yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Loans;


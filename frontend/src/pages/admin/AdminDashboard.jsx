import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import MetricCard from '../../components/MetricCard';
import Alert from '../../components/Alert';
import {
  Users,
  Wallet,
  ArrowLeftRight,
  TrendingUp,
  FileCheck,
  ShieldAlert,
  ArrowRight,
  Lock,
  BarChart3,
  FileSpreadsheet,
  RefreshCw,
} from 'lucide-react';

const AdminDashboard = () => {
  const [kpis, setKpis] = useState(null);
  const [excelStatus, setExcelStatus] = useState(null);
  const [downloadingExcel, setDownloadingExcel] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDashboard = () => {
    Promise.all([
      adminAPI.getDashboardKPIs(),
      adminAPI.getExcelStatus().catch(() => ({ data: null })),
    ])
      .then(([kpiRes, excelRes]) => {
        setKpis(kpiRes.data);
        setExcelStatus(excelRes.data);
      })
      .catch(() => setError('Failed to load bank overview metrics.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDashboard();
    const timer = setInterval(() => {
      adminAPI.getExcelStatus().then((res) => setExcelStatus(res.data)).catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const handleDownloadExcel = async () => {
    try {
      setDownloadingExcel(true);
      const res = await adminAPI.downloadExcel();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `FinTrack_Live_Database_${new Date().toISOString().slice(0, 10)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      adminAPI.getExcelStatus().then((s) => setExcelStatus(s.data)).catch(() => {});
    } catch (err) {
      setError('Failed to export live Excel workbook.');
    } finally {
      setDownloadingExcel(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Administrator Overview Console</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational KPIs, pending credit approvals, compliance reviews, and database analytics
          </p>
          {excelStatus?.exists && (
            <p className="text-xs text-emerald-700 font-medium mt-1.5 flex items-center gap-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>
                Live Excel Auto-Sync Active ({excelStatus.file_name} • {excelStatus.size_kb} KB • Updated{' '}
                {new Date(excelStatus.last_updated).toLocaleTimeString()})
              </span>
            </p>
          )}
        </div>
        <button
          onClick={handleDownloadExcel}
          disabled={downloadingExcel}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition disabled:opacity-60"
        >
          {downloadingExcel ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <FileSpreadsheet className="w-4 h-4" />
          )}
          <span>{downloadingExcel ? 'Generating Excel...' : 'Download Live Excel (.xlsx)'}</span>
        </button>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricCard
          title="Total Registered Customers"
          value={kpis?.total_customers || 0}
          subtitle="Active KYC Profiles"
          icon={Users}
          color="blue"
        />
        <MetricCard
          title="Total Bank Accounts"
          value={kpis?.total_accounts || 0}
          subtitle="Savings & Checking"
          icon={Wallet}
          color="slate"
        />
        <MetricCard
          title="Total Successful Transfers"
          value={kpis?.total_transactions || 0}
          subtitle="Balanced Ledger Records"
          icon={ArrowLeftRight}
          color="slate"
        />
        <MetricCard
          title="Total Transaction Volume"
          value={`₹${parseFloat(kpis?.total_volume || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
          subtitle="Cumulative Transferred"
          icon={TrendingUp}
          color="emerald"
        />
        <MetricCard
          title="Pending Loan Requests"
          value={kpis?.pending_loans || 0}
          subtitle="Awaiting Officer Review"
          icon={FileCheck}
          color={kpis?.pending_loans > 0 ? 'amber' : 'slate'}
        />
        <MetricCard
          title="Open Fraud Alerts"
          value={kpis?.pending_fraud_reviews || 0}
          subtitle="Rule-Flagged Holds"
          icon={ShieldAlert}
          color={kpis?.pending_fraud_reviews > 0 ? 'rose' : 'slate'}
        />
      </div>

      {/* Quick Action Navigation Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
        <Link
          to="/admin/loans"
          className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow card-shadow-hover flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-accent flex items-center justify-center mb-3">
              <FileCheck className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900">Loan Approvals</h3>
            <p className="text-xs text-slate-500 mt-1">
              Review personal loan applications, verify 50% income debt caps, and approve or reject.
            </p>
          </div>
          <div className="mt-4 flex items-center text-xs font-bold text-accent">
            <span>Manage Applications</span>
            <ArrowRight className="w-4 h-4 ml-1" />
          </div>
        </Link>

        <Link
          to="/admin/fraud"
          className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow card-shadow-hover flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-3">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900">Fraud Compliance</h3>
            <p className="text-xs text-slate-500 mt-1">
              Inspect rule-flagged transfers $\ge$ ₹10,000. Approve to release funds atomically or reject without money movement.
            </p>
          </div>
          <div className="mt-4 flex items-center text-xs font-bold text-amber-600">
            <span>Review Flagged Transfers</span>
            <ArrowRight className="w-4 h-4 ml-1" />
          </div>
        </Link>

        <Link
          to="/admin/audit"
          className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow card-shadow-hover flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center mb-3">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900">Security Audit Logs</h3>
            <p className="text-xs text-slate-500 mt-1">
              Inspect immutable MongoDB audit events synced via PostgreSQL Transactional Outbox.
            </p>
          </div>
          <div className="mt-4 flex items-center text-xs font-bold text-slate-700">
            <span>View Audit Logs</span>
            <ArrowRight className="w-4 h-4 ml-1" />
          </div>
        </Link>
      </div>
    </div>
  );
};

export default AdminDashboard;


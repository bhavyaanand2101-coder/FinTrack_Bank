import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../api/client';
import Alert from '../../components/Alert';
import { BarChart3, Download, Users, Moon, Calendar } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

const Reports = () => {
  const [reports, setReports] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    adminAPI
      .getAdvancedReports()
      .then((res) => setReports(res.data))
      .catch(() => setError('Failed to generate analytical reports.'))
      .finally(() => setLoading(false));
  }, []);

  const handleExportTopCustomers = () => {
    if (!reports?.top_customers) return;
    const headers = ['Customer ID', 'Full Name', 'Email', 'Transfers Sent', 'Total Transferred (INR)'];
    const rows = reports.top_customers.map((c) => [
      c.customer_id,
      `"${c.full_name}"`,
      c.email,
      c.total_transfers_sent,
      c.total_amount_transferred,
    ]);
    downloadCSV([headers.join(','), ...rows.map((r) => r.join(','))].join('\n'), 'Top_Customers_Report.csv');
  };

  const handleExportDormantAccounts = () => {
    if (!reports?.dormant_accounts) return;
    const headers = ['Account ID', 'Customer Name', 'Customer Email', 'Account Type', 'Balance', 'Created Date'];
    const rows = reports.dormant_accounts.map((a) => [
      a.account_id,
      `"${a.customer_name}"`,
      a.customer_email,
      a.account_type,
      a.balance,
      new Date(a.created_at).toISOString(),
    ]);
    downloadCSV([headers.join(','), ...rows.map((r) => r.join(','))].join('\n'), 'Dormant_Accounts_Report.csv');
  };

  const downloadCSV = (content, filename) => {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const monthlyChartData = (reports?.monthly_volume || []).map((m) => ({
    month: m.month_label,
    volume: parseFloat(m.total_volume),
    transfers: m.transfer_count,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Advanced Analytical SQL Reports</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Academic DBMS complex query demonstrations: CTEs, Subqueries, Window Functions, and LEFT JOINs
          </p>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {/* Monthly System-Wide Transaction Volume (CTE Query 2) */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">System Transaction Volume (CTE Aggregation)</h3>
            <p className="text-xs text-slate-500">Query 2: WITH monthly_metrics AS (SELECT ... GROUP BY DATE_TRUNC)</p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-blue-50 text-accent">Query 2 (CTE)</span>
        </div>

        <div className="h-64">
          {monthlyChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyChartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#64748B' }} />
                <YAxis tick={{ fontSize: 12, fill: '#64748B' }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip
                  formatter={(val) => [`₹${parseFloat(val).toLocaleString('en-IN')}`, 'Total Volume']}
                  contentStyle={{ backgroundColor: '#0F172A', color: '#FFF', borderRadius: '8px', border: 'none' }}
                />
                <Bar dataKey="volume" fill="#2563EB" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-slate-400">
              No historical data available.
            </div>
          )}
        </div>
      </div>

      {/* Top 5 Customers by Transfer Volume (Query 4) */}
      <div className="bg-white rounded-2xl border border-slate-200 card-shadow overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">Top 5 Customers by Transfer Volume</h3>
            <p className="text-xs text-slate-500">Query 4: Subquery + GROUP BY + ORDER BY SUM(t.amount) DESC</p>
          </div>
          <button
            onClick={handleExportTopCustomers}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
              <tr>
                <th className="py-3 px-4">Rank</th>
                <th className="py-3 px-4">Customer Name</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4">Transfers Sent</th>
                <th className="py-3 px-4 text-right">Total Transferred</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(reports?.top_customers || []).map((c, idx) => (
                <tr key={c.customer_id} className="hover:bg-slate-50 transition">
                  <td className="py-3 px-4 font-bold text-accent">#{idx + 1}</td>
                  <td className="py-3 px-4 font-semibold text-slate-900">{c.full_name}</td>
                  <td className="py-3 px-4 text-xs text-slate-500">{c.email}</td>
                  <td className="py-3 px-4 text-xs font-medium text-slate-700">{c.total_transfers_sent} transfers</td>
                  <td className="py-3 px-4 text-right font-extrabold text-slate-900">
                    ₹{parseFloat(c.total_amount_transferred).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dormant Accounts Detection (Query 5) */}
      <div className="bg-white rounded-2xl border border-slate-200 card-shadow overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">Dormant Accounts Detection</h3>
            <p className="text-xs text-slate-500">Query 5: LEFT JOIN accounts with transactions WHERE tx.id IS NULL</p>
          </div>
          <button
            onClick={handleExportDormantAccounts}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
              <tr>
                <th className="py-3 px-4">Account ID</th>
                <th className="py-3 px-4">Account Holder</th>
                <th className="py-3 px-4">Holder Email</th>
                <th className="py-3 px-4">Account Type</th>
                <th className="py-3 px-4">Created Date</th>
                <th className="py-3 px-4 text-right">Idle Balance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(reports?.dormant_accounts || []).length > 0 ? (
                reports.dormant_accounts.map((acc) => (
                  <tr key={acc.account_id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">#{acc.account_id}</td>
                    <td className="py-3 px-4 font-semibold text-slate-900">{acc.customer_name}</td>
                    <td className="py-3 px-4 text-xs text-slate-500">{acc.customer_email}</td>
                    <td className="py-3 px-4 text-xs font-semibold text-slate-700">{acc.account_type}</td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(acc.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right font-bold text-slate-900">
                      ₹{parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-xs text-slate-400">
                    No dormant accounts detected. All accounts have active transactions.
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

export default Reports;


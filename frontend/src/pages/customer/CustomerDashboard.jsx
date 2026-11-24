import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { accountsAPI } from '../../api/client';
import MetricCard from '../../components/MetricCard';
import StatusBadge from '../../components/StatusBadge';
import Alert from '../../components/Alert';
import {
  Wallet,
  ArrowUpRight,
  ArrowDownLeft,
  Activity,
  Calendar,
  CreditCard,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
} from 'recharts';

const CustomerDashboard = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [statement, setStatement] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId) {
      loadStatement(selectedAccountId);
    }
  }, [selectedAccountId]);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const res = await accountsAPI.getAccounts();
      setAccounts(res.data);
      if (res.data.length > 0) {
        setSelectedAccountId(res.data[0].account_id);
      }
    } catch (err) {
      setError('Failed to load accounts. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const loadStatement = async (accId) => {
    try {
      const [stmtRes, sumRes] = await Promise.all([
        accountsAPI.getAccountStatement(accId, 20),
        accountsAPI.getAccountSummary(accId).catch(() => ({ data: null })),
      ]);
      setStatement(stmtRes.data);
      setSummary(sumRes.data);
    } catch (err) {
      setError('Failed to fetch account metrics.');
    }
  };

  const activeAccount = accounts.find((a) => a.account_id === selectedAccountId);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Format chart data for monthly spending
  const monthlyData = (statement?.monthly_spending || []).map((m) => ({
    month: m.month_label,
    amount: parseFloat(m.total_monthly_outgoing),
    count: m.transfer_count,
  }));

  // Format running balance chronological data
  const runningData = [...(statement?.running_balance || [])]
    .reverse()
    .map((r) => ({
      time: new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      balance: parseFloat(r.running_balance),
    }));

  return (
    <div className="space-y-6">
      {/* Top Header & Account Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Customer Financial Dashboard</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Welcome back, <span className="font-semibold text-slate-800">{user?.full_name}</span> (Customer #{user?.customer_id})
          </p>
        </div>

        {accounts.length > 0 && (
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-slate-500">Active Account:</span>
            <select
              value={selectedAccountId || ''}
              onChange={(e) => setSelectedAccountId(Number(e.target.value))}
              className="bg-slate-50 border border-slate-200 text-slate-900 text-sm font-semibold rounded-xl px-3 py-2 focus:ring-2 focus:ring-accent focus:outline-none"
            >
              {accounts.map((acc) => (
                <option key={acc.account_id} value={acc.account_id}>
                  #{acc.account_id} – {acc.account_type} (₹{parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {/* KPI Cards */}
      {activeAccount && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Available Balance"
            value={`₹${parseFloat(activeAccount.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
            subtitle={activeAccount.currency}
            icon={Wallet}
            color="blue"
          />
          <MetricCard
            title="Account Status"
            value={activeAccount.is_frozen ? 'Frozen' : 'Active'}
            subtitle={activeAccount.account_type}
            icon={Activity}
            color={activeAccount.is_frozen ? 'rose' : 'emerald'}
          />
          <MetricCard
            title="Total Incoming"
            value={`₹${parseFloat(summary?.total_incoming_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
            subtitle="Credits Received"
            icon={ArrowDownLeft}
            color="emerald"
          />
          <MetricCard
            title="Total Outgoing"
            value={`₹${parseFloat(summary?.total_outgoing_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
            subtitle={`${summary?.total_transactions_count || 0} Transfers Sent`}
            icon={ArrowUpRight}
            color="rose"
          />
        </div>
      )}

      {/* Analytical Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Spending (CTE Query 2) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Monthly Spending (CTE Breakdown)</h3>
              <p className="text-xs text-slate-500">Advanced SQL Query 2: Aggregate monthly debits</p>
            </div>
            <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600">
              Query 2 (CTE)
            </span>
          </div>

          <div className="h-64">
            {monthlyData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#64748B' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#64748B' }} tickFormatter={(v) => `₹${v}`} />
                  <Tooltip
                    formatter={(val) => [`₹${parseFloat(val).toLocaleString('en-IN')}`, 'Outgoing Spending']}
                    contentStyle={{ backgroundColor: '#0F172A', color: '#FFF', borderRadius: '8px', border: 'none' }}
                  />
                  <Bar dataKey="amount" fill="#2563EB" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No monthly transactions recorded yet.
              </div>
            )}
          </div>
        </div>

        {/* Running Balance (Window Function Query 1) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Running Balance (Window Function)</h3>
              <p className="text-xs text-slate-500">Advanced SQL Query 1: SUM(...) OVER (PARTITION BY account_id)</p>
            </div>
            <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600">
              Query 1 (Window)
            </span>
          </div>

          <div className="h-64">
            {runningData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={runningData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="time" tick={{ fontSize: 12, fill: '#64748B' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#64748B' }} tickFormatter={(v) => `₹${v}`} />
                  <Tooltip
                    formatter={(val) => [`₹${parseFloat(val).toLocaleString('en-IN')}`, 'Balance']}
                    contentStyle={{ backgroundColor: '#0F172A', color: '#FFF', borderRadius: '8px', border: 'none' }}
                  />
                  <Line type="monotone" dataKey="balance" stroke="#059669" strokeWidth={2.5} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No balance ledger entries found.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Activity Table */}
      <div className="bg-white rounded-2xl border border-slate-200 card-shadow overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">Recent Account Activity</h3>
          <span className="text-xs text-slate-500 font-medium">Last 10 transactions</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
              <tr>
                <th className="py-3 px-4">Tx ID</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Counterparty</th>
                <th className="py-3 px-4">Direction</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(statement?.transactions || []).length > 0 ? (
                statement.transactions.slice(0, 10).map((tx) => (
                  <tr key={tx.transaction_id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">#{tx.transaction_id}</td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(tx.transaction_date).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      {tx.direction === 'DEBIT' ? tx.receiver_name : tx.sender_name}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={tx.direction} />
                    </td>
                    <td
                      className={`py-3 px-4 font-bold ${
                        tx.direction === 'DEBIT' ? 'text-rose-600' : 'text-emerald-600'
                      }`}
                    >
                      {tx.direction === 'DEBIT' ? '-' : '+'}₹
                      {parseFloat(tx.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={tx.status} />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600 max-w-xs truncate">{tx.description}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-xs text-slate-400">
                    No transactions recorded for this account.
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

export default CustomerDashboard;


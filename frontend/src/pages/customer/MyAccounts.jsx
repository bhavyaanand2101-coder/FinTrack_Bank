import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { accountsAPI } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import Alert from '../../components/Alert';
import { Wallet, ArrowLeftRight, Clock, ShieldCheck, Snowflake } from 'lucide-react';

const MyAccounts = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    accountsAPI
      .getAccounts()
      .then((res) => setAccounts(res.data))
      .catch(() => setError('Failed to load your bank accounts.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">My Bank Accounts</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Overview of all active accounts registered under your customer profile
          </p>
        </div>
        <Link
          to="/transfers"
          className="inline-flex items-center space-x-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-semibold rounded-xl transition shadow-sm"
        >
          <ArrowLeftRight className="w-4 h-4" />
          <span>Transfer Funds</span>
        </Link>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {accounts.map((acc) => (
          <div
            key={acc.account_id}
            className={`bg-white rounded-2xl border p-6 card-shadow card-shadow-hover relative overflow-hidden ${
              acc.is_frozen ? 'border-rose-200 bg-rose-50/20' : 'border-slate-200'
            }`}
          >
            {/* Top Bar */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div
                  className={`p-3 rounded-xl ${
                    acc.is_frozen ? 'bg-rose-100 text-rose-600' : 'bg-blue-50 text-accent'
                  }`}
                >
                  {acc.is_frozen ? <Snowflake className="w-6 h-6" /> : <Wallet className="w-6 h-6" />}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900">
                    {acc.account_type} Account
                  </h3>
                  <p className="text-xs font-mono text-slate-500">Account #{acc.account_id}</p>
                </div>
              </div>

              <StatusBadge status={acc.is_frozen ? 'FROZEN' : 'ACTIVE'} />
            </div>

            {/* Balance */}
            <div className="my-6">
              <p className="text-xs font-semibold uppercase text-slate-400">Available Balance</p>
              <div className="flex items-baseline space-x-2 mt-1">
                <span className="text-3xl font-extrabold text-slate-900">
                  ₹{parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <span className="text-sm font-semibold text-slate-500">{acc.currency}</span>
              </div>
            </div>

            {/* Footer Info */}
            <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <span className="inline-flex items-center">
                <Clock className="w-3.5 h-3.5 mr-1 text-slate-400" />
                Created: {new Date(acc.created_at).toLocaleDateString()}
              </span>
              <span className="inline-flex items-center text-emerald-600 font-semibold">
                <ShieldCheck className="w-3.5 h-3.5 mr-1" />
                Overdraft Protected
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MyAccounts;


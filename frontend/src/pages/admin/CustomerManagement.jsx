import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import ConfirmationModal from '../../components/ConfirmationModal';
import Alert from '../../components/Alert';
import { Users, Search, Snowflake, Sun, Shield, Wallet } from 'lucide-react';

const CustomerManagement = () => {
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Freeze Modal State
  const [modalState, setModalState] = useState({
    isOpen: false,
    accountId: null,
    freeze: false,
    customerName: '',
  });

  useEffect(() => {
    loadCustomers();
  }, [search]);

  const loadCustomers = async () => {
    try {
      setLoading(true);
      const res = await adminAPI.getCustomers(search);
      setCustomers(res.data);
    } catch (err) {
      setError('Failed to fetch customers.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFreeze = (accountId, currentlyFrozen, customerName) => {
    setModalState({
      isOpen: true,
      accountId,
      freeze: !currentlyFrozen,
      customerName,
    });
  };

  const handleConfirmFreeze = async () => {
    const { accountId, freeze } = modalState;
    setModalState({ ...modalState, isOpen: false });

    try {
      const res = await adminAPI.toggleAccountFreeze(accountId, freeze);
      setSuccess(res.data.message);
      loadCustomers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update account freeze status.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Customer & Account Management</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Inspect KYC profiles, verify account ownership, and manage account lock/freeze statuses
          </p>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {/* Search Input */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 card-shadow">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by full name, email, or phone number..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>
      </div>

      {/* Customer List */}
      <div className="space-y-4">
        {loading ? (
          <div className="text-center py-12 text-xs text-slate-400">Loading customer profiles...</div>
        ) : customers.length > 0 ? (
          customers.map((cust) => (
            <div
              key={cust.customer_id}
              className="bg-white rounded-2xl border border-slate-200 p-6 card-shadow space-y-4"
            >
              {/* Customer Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-100 gap-2">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 text-accent flex items-center justify-center font-bold text-sm">
                    {cust.full_name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">{cust.full_name}</h3>
                    <p className="text-xs text-slate-500">
                      Customer ID #{cust.customer_id} • Email: {cust.email} • Phone: {cust.phone}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-slate-400">
                  Registered: {new Date(cust.created_at).toLocaleDateString()}
                </span>
              </div>

              {/* Accounts Owned by Customer */}
              <div>
                <p className="text-xs font-bold uppercase text-slate-400 mb-2">Registered Accounts:</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {(cust.accounts || []).map((acc) => (
                    <div
                      key={acc.account_id}
                      className={`p-4 rounded-xl border flex items-center justify-between ${
                        acc.is_frozen ? 'bg-rose-50/30 border-rose-200' : 'bg-slate-50 border-slate-200'
                      }`}
                    >
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-bold text-slate-800">#{acc.account_id}</span>
                          <span className="text-xs text-slate-500">({acc.account_type})</span>
                        </div>
                        <p className="text-base font-extrabold text-slate-900 mt-1">
                          ₹{parseFloat(acc.balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </p>
                        <div className="mt-1">
                          <StatusBadge status={acc.is_frozen ? 'FROZEN' : 'ACTIVE'} />
                        </div>
                      </div>

                      <button
                        onClick={() => handleToggleFreeze(acc.account_id, acc.is_frozen, cust.full_name)}
                        className={`p-2 rounded-lg text-xs font-semibold flex items-center space-x-1 transition ${
                          acc.is_frozen
                            ? 'bg-emerald-100 hover:bg-emerald-200 text-emerald-800'
                            : 'bg-rose-100 hover:bg-rose-200 text-rose-800'
                        }`}
                        title={acc.is_frozen ? 'Unfreeze Account' : 'Freeze Account'}
                      >
                        {acc.is_frozen ? (
                          <>
                            <Sun className="w-3.5 h-3.5 mr-1" />
                            <span>Unfreeze</span>
                          </>
                        ) : (
                          <>
                            <Snowflake className="w-3.5 h-3.5 mr-1" />
                            <span>Freeze</span>
                          </>
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-xs text-slate-400">
            No customers found matching search query.
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={modalState.isOpen}
        title={modalState.freeze ? 'Freeze Customer Account' : 'Unfreeze Customer Account'}
        message={
          modalState.freeze
            ? `Are you sure you want to freeze Account #${modalState.accountId} (${modalState.customerName})? The account will be immediately blocked from transfers and debits.`
            : `Are you sure you want to unfreeze Account #${modalState.accountId} (${modalState.customerName})? Normal transactions will be re-enabled.`
        }
        confirmText={modalState.freeze ? 'Yes, Freeze Account' : 'Yes, Unfreeze Account'}
        confirmVariant={modalState.freeze ? 'danger' : 'primary'}
        onConfirm={handleConfirmFreeze}
        onClose={() => setModalState({ ...modalState, isOpen: false })}
      />
    </div>
  );
};

export default CustomerManagement;


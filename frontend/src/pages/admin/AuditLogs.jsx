import React, { useEffect, useState } from 'react';
import { auditAPI } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import Alert from '../../components/Alert';
import {
  Lock,
  RefreshCw,
  Search,
  Filter,
  CheckCircle,
  Clock,
  ChevronLeft,
  ChevronRight,
  Code2,
} from 'lucide-react';

const AuditLogs = () => {
  const [logsData, setLogsData] = useState({ logs: [], outbox: {}, total_count: 0 });
  const [actionFilter, setActionFilter] = useState('');
  const [limit] = useState(25);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Selected JSON Inspector modal
  const [selectedEvent, setSelectedEvent] = useState(null);

  useEffect(() => {
    loadAuditLogs();
  }, [actionFilter, skip]);

  const loadAuditLogs = async () => {
    try {
      setLoading(true);
      const params = { limit, skip };
      if (actionFilter) params.action = actionFilter;

      const res = await auditAPI.getAuditLogs(params);
      setLogsData(res.data);
    } catch (err) {
      setError('Failed to fetch security audit logs from MongoDB.');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncOutbox = async () => {
    try {
      setSyncing(true);
      setError('');
      setSuccess('');
      const res = await auditAPI.triggerOutboxSync();
      setSuccess(res.data.message);
      loadAuditLogs();
    } catch (err) {
      setError('Outbox synchronization pass encountered an error.');
    } finally {
      setSyncing(false);
    }
  };

  const outbox = logsData.outbox || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Security Audit Logs (MongoDB)</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Immutable append-only audit trail synchronized from PostgreSQL Transactional Outbox
          </p>
        </div>

        <button
          onClick={handleSyncOutbox}
          disabled={syncing}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-xs font-bold rounded-xl transition shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          <span>{syncing ? 'Syncing Outbox...' : 'Trigger Outbox Sync'}</span>
        </button>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {/* Outbox Status Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 bg-white rounded-xl border border-slate-200 card-shadow">
          <span className="text-xs font-semibold text-slate-400 uppercase">Outbox Pending</span>
          <p className="text-xl font-extrabold text-slate-800 mt-0.5">{outbox.pending || 0}</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200 card-shadow">
          <span className="text-xs font-semibold text-slate-400 uppercase">Processing</span>
          <p className="text-xl font-extrabold text-blue-600 mt-0.5">{outbox.processing || 0}</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200 card-shadow">
          <span className="text-xs font-semibold text-slate-400 uppercase">Delivered to Mongo</span>
          <p className="text-xl font-extrabold text-emerald-600 mt-0.5">{outbox.delivered || 0}</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200 card-shadow">
          <span className="text-xs font-semibold text-slate-400 uppercase">Delivery Retries</span>
          <p className="text-xl font-extrabold text-rose-600 mt-0.5">{outbox.failed || 0}</p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 card-shadow flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setSkip(0);
            }}
            className="bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-800 rounded-xl px-3 py-2 focus:ring-2 focus:ring-accent"
          >
            <option value="">All Action Types</option>
            <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
            <option value="LOGIN_FAILED">LOGIN_FAILED</option>
            <option value="TRANSFER_COMPLETED">TRANSFER_COMPLETED</option>
            <option value="TRANSFER_FLAGGED">TRANSFER_FLAGGED</option>
            <option value="LOAN_APPLICATION_SUBMITTED">LOAN_APPLICATION_SUBMITTED</option>
            <option value="LOAN_DECISION">LOAN_DECISION</option>
            <option value="FRAUD_ALERT_APPROVED">FRAUD_ALERT_APPROVED</option>
            <option value="FRAUD_ALERT_REJECTED">FRAUD_ALERT_REJECTED</option>
            <option value="ACCOUNT_FROZEN">ACCOUNT_FROZEN</option>
            <option value="ACCOUNT_UNFROZEN">ACCOUNT_UNFROZEN</option>
          </select>
        </div>

        <span className="text-xs text-slate-500 font-medium">
          Total Logs: <strong>{logsData.total_count || 0}</strong> events
        </span>
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-2xl border border-slate-200 card-shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
              <tr>
                <th className="py-3 px-4">Event ID</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Action Type</th>
                <th className="py-3 px-4">Customer ID</th>
                <th className="py-3 px-4">Account ID</th>
                <th className="py-3 px-4">IP Address</th>
                <th className="py-3 px-4 text-right">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-xs text-slate-400">
                    Loading security logs from MongoDB...
                  </td>
                </tr>
              ) : (logsData.logs || []).length > 0 ? (
                logsData.logs.map((log) => (
                  <tr key={log.event_id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-mono text-xs text-slate-600 truncate max-w-[120px]">
                      {log.event_id}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {log.customer_id ? `#${log.customer_id}` : '—'}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {log.account_id ? `#${log.account_id}` : '—'}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-500">{log.ip_address || '127.0.0.1'}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedEvent(log)}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
                      >
                        <Code2 className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-xs text-slate-400">
                    No audit logs found matching the filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span>
            Showing records {skip + 1} to {Math.min(skip + limit, logsData.total_count || 0)}
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setSkip(Math.max(0, skip - limit))}
              disabled={skip === 0}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setSkip(skip + limit)}
              disabled={skip + limit >= (logsData.total_count || 0)}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-30"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Raw Document JSON Inspector Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 text-slate-100 rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-slate-800">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <h3 className="text-sm font-mono font-bold text-accent">
                MongoDB Document: {selectedEvent.event_id}
              </h3>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800"
              >
                Close (ESC)
              </button>
            </div>

            <pre className="text-xs font-mono bg-slate-950 p-4 rounded-xl overflow-x-auto max-h-96 text-emerald-400">
              {JSON.stringify(selectedEvent, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditLogs;


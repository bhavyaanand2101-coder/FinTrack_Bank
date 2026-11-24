import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  accountsAPI,
  adminAPI,
  auditAPI,
  fraudAPI,
  liveSheetAPI,
  transfersAPI,
} from '../api/client';
import StatusBadge from '../components/StatusBadge';
import Alert from '../components/Alert';
import {
  FileSpreadsheet,
  Download,
  Pause,
  Play,
  RefreshCw,
  Search,
  Zap,
  CheckCircle2,
  XCircle,
  Send,
  ShieldAlert,
  Database,
} from 'lucide-react';

const CURRENCY_COLS = new Set([
  'balance',
  'amount',
  'transfer_amount',
  'requested_amount',
  'annual_income',
  'total_incoming_amount',
  'total_outgoing_amount',
]);

const STATUS_COLS = new Set([
  'status',
  'alert_status',
  'transaction_status',
  'entry_type',
  'is_frozen',
]);

const colIndexToExcelLetter = (index) => {
  let letter = '';
  let n = index;
  while (n >= 0) {
    letter = String.fromCharCode((n % 26) + 65) + letter;
    n = Math.floor(n / 26) - 1;
  }
  return letter;
};

const formatCurrency = (val) => {
  const num = Number(val);
  if (Number.isNaN(num)) return String(val ?? '');
  return `₹${num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const LiveExcelSheet = () => {
  const { user, isAdmin, isCustomer } = useAuth();
  const [snapshot, setSnapshot] = useState(null);
  const [activeSheet, setActiveSheet] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [connectionState, setConnectionState] = useState('CONNECTING'); // CONNECTING | LIVE | POLLING | PAUSED
  const [selectedCell, setSelectedCell] = useState(null);
  const [downloading, setDownloading] = useState(false);

  // Real-time diff state (flashes changed cells/rows when ACID transactions commit)
  const [diffState, setDiffState] = useState({
    newRows: {},        // { sheetName: Set(rowKey) }
    changedCells: {},   // { sheetName: { "rowKey::col": { oldVal, newVal, delta } } }
    sheetBadges: {},    // { sheetName: count }
  });
  const [acidLog, setAcidLog] = useState([]);

  // Live ACID Demo controls state
  const [txSender, setTxSender] = useState('');
  const [txReceiver, setTxReceiver] = useState('1003');
  const [txAmount, setTxAmount] = useState('500');
  const [txDesc, setTxDesc] = useState('Live Real-Time ACID Transfer');
  const [actionBusy, setActionBusy] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  const prevSnapshotRef = useRef(null);
  const clearDiffTimerRef = useRef(null);
  const isPausedRef = useRef(isPaused);
  isPausedRef.current = isPaused;

  const applySnapshot = useCallback((nextSnap) => {
    if (!nextSnap || !nextSnap.sheets) return;

    const prevSnap = prevSnapshotRef.current;

    if (prevSnap && prevSnap.fingerprint !== nextSnap.fingerprint) {
      const nextNewRows = {};
      const nextChangedCells = {};
      const nextBadges = {};
      const summaryParts = [];

      Object.entries(nextSnap.sheets).forEach(([sheetName, sheetObj]) => {
        const prevSheet = prevSnap.sheets?.[sheetName];
        if (!prevSheet) return;

        const keyField = sheetObj.key_field;
        const prevMap = new Map();
        prevSheet.rows.forEach((r) => prevMap.set(String(r[keyField]), r));

        const addedSet = new Set();
        const cellDiffMap = {};
        let updatedRowCount = 0;

        sheetObj.rows.forEach((row) => {
          const rowKey = String(row[keyField]);
          const oldRow = prevMap.get(rowKey);

          if (!oldRow) {
            addedSet.add(rowKey);
          } else {
            let rowModified = false;
            sheetObj.columns.forEach((col) => {
              const oldVal = oldRow[col];
              const newVal = row[col];
              if (String(oldVal ?? '') !== String(newVal ?? '')) {
                rowModified = true;
                let delta = null;
                if (CURRENCY_COLS.has(col)) {
                  const nOld = Number(oldVal);
                  const nNew = Number(newVal);
                  if (!Number.isNaN(nOld) && !Number.isNaN(nNew)) {
                    delta = Number((nNew - nOld).toFixed(2));
                  }
                }
                cellDiffMap[`${rowKey}::${col}`] = { oldVal, newVal, delta };
              }
            });
            if (rowModified) updatedRowCount += 1;
          }
        });

        const totalChanges = addedSet.size + updatedRowCount;
        if (totalChanges > 0) {
          nextNewRows[sheetName] = addedSet;
          nextChangedCells[sheetName] = cellDiffMap;
          nextBadges[sheetName] = totalChanges;

          const parts = [];
          if (addedSet.size > 0) parts.push(`+${addedSet.size} new`);
          if (updatedRowCount > 0) parts.push(`${updatedRowCount} updated`);
          summaryParts.push(`${sheetName} (${parts.join(', ')})`);
        }
      });

      if (summaryParts.length > 0) {
        setDiffState({
          newRows: nextNewRows,
          changedCells: nextChangedCells,
          sheetBadges: nextBadges,
        });

        setAcidLog((prev) => [
          {
            id: `${nextSnap.fingerprint}-${Date.now()}`,
            time: new Date(nextSnap.timestamp).toLocaleTimeString(),
            summary: summaryParts.join(' • '),
          },
          ...prev.slice(0, 7),
        ]);

        if (clearDiffTimerRef.current) clearTimeout(clearDiffTimerRef.current);
        clearDiffTimerRef.current = setTimeout(() => {
          setDiffState({ newRows: {}, changedCells: {}, sheetBadges: {} });
        }, 7000);
      }
    }

    prevSnapshotRef.current = nextSnap;
    setSnapshot(nextSnap);

    // Initialize default active sheet and customer sender account
    const sheetNames = Object.keys(nextSnap.sheets);
    setActiveSheet((curr) => (curr && nextSnap.sheets[curr] ? curr : sheetNames[0]));

    if (nextSnap.scope === 'CUSTOMER' && nextSnap.sheets.My_Accounts?.rows?.length > 0) {
      setTxSender((curr) => curr || String(nextSnap.sheets.My_Accounts.rows[0].account_id));
    }
  }, []);

  // Connect to Real-Time SSE stream (with graceful polling fallback)
  useEffect(() => {
    const token = localStorage.getItem('fintrack_token');
    if (!token) return;

    let es = null;
    let pollTimer = null;

    const startPollingFallback = () => {
      setConnectionState('POLLING');
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(async () => {
        if (isPausedRef.current) return;
        try {
          const fp = prevSnapshotRef.current?.fingerprint || null;
          const res = await liveSheetAPI.getSnapshot(fp);
          if (res.data?.changed) {
            applySnapshot(res.data);
          }
        } catch {
          // silent retry on next tick
        }
      }, 1000);
    };

    // Initial immediate snapshot load
    liveSheetAPI
      .getSnapshot()
      .then((res) => applySnapshot(res.data))
      .catch(() => setFeedback({ type: 'error', message: 'Failed to load live spreadsheet data.' }));

    // Open real-time SSE stream
    try {
      const streamUrl = liveSheetAPI.getStreamUrl(token);
      es = new EventSource(streamUrl);

      es.onopen = () => {
        if (!isPausedRef.current) setConnectionState('LIVE');
      };

      es.addEventListener('snapshot', (evt) => {
        if (isPausedRef.current) return;
        try {
          const parsed = JSON.parse(evt.data);
          setConnectionState('LIVE');
          applySnapshot(parsed);
        } catch {
          // ignore malformed frames
        }
      });

      es.onerror = () => {
        if (es) {
          es.close();
          es = null;
        }
        startPollingFallback();
      };
    } catch {
      startPollingFallback();
    }

    return () => {
      if (es) es.close();
      if (pollTimer) clearInterval(pollTimer);
      if (clearDiffTimerRef.current) clearTimeout(clearDiffTimerRef.current);
    };
  }, [applySnapshot]);

  const handleTogglePause = () => {
    setIsPaused((prev) => {
      const next = !prev;
      setConnectionState(next ? 'PAUSED' : 'LIVE');
      if (!next) {
        liveSheetAPI.getSnapshot().then((res) => applySnapshot(res.data)).catch(() => {});
      }
      return next;
    });
  };

  const handleManualRefresh = async () => {
    try {
      const res = await liveSheetAPI.getSnapshot();
      applySnapshot(res.data);
    } catch {
      setFeedback({ type: 'error', message: 'Failed to refresh live data.' });
    }
  };

  const handleDownloadXlsx = async () => {
    try {
      setDownloading(true);
      const res = isAdmin
        ? await adminAPI.downloadExcel()
        : await accountsAPI.downloadMyExcel();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        isAdmin
          ? `FinTrack_Live_Database_${new Date().toISOString().slice(0, 10)}.xlsx`
          : `FinTrack_${user?.username}_Live_${new Date().toISOString().slice(0, 10)}.xlsx`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setFeedback({ type: 'error', message: 'Failed to download .xlsx workbook.' });
    } finally {
      setDownloading(false);
    }
  };

  // Customer Live ACID Transfer trigger
  const handleRunAcidTransfer = async (e, overrideAmount = null) => {
    if (e) e.preventDefault();
    const amountVal = Number(overrideAmount !== null ? overrideAmount : txAmount);
    if (!txSender || !txReceiver || Number.isNaN(amountVal) || amountVal <= 0) {
      setFeedback({ type: 'error', message: 'Enter valid sender, receiver account ID, and positive amount.' });
      return;
    }

    setActionBusy(true);
    setFeedback({ type: '', message: '' });
    try {
      const res = await transfersAPI.executeTransfer({
        sender_account_id: Number(txSender),
        receiver_account_id: Number(txReceiver),
        amount: amountVal,
        description: txDesc || 'Live Real-Time ACID Transfer',
        idempotency_key: crypto.randomUUID(),
      });
      const data = res.data;
      if (data.status === 'FLAGGED') {
        setFeedback({
          type: 'warning',
          message: `ACID Compliance Hold: Transfer #${data.transaction_id} (₹${amountVal.toLocaleString('en-IN')}) FLAGGED — ZERO balance deducted! Watch My_Transactions update live.`,
        });
      } else {
        setFeedback({
          type: 'success',
          message: `ACID Commit OK: Tx #${data.transaction_id} transferred ₹${amountVal.toLocaleString('en-IN')} — Watch My_Accounts, My_Transactions & My_Ledger_Entries flash live!`,
        });
      }
      // Pull immediately so highlight feels instantaneous
      const snap = await liveSheetAPI.getSnapshot();
      applySnapshot(snap.data);
    } catch (err) {
      setFeedback({
        type: 'error',
        message: `ACID Rollback Triggered: ${err.response?.data?.detail || 'Transaction rejected and rolled back safely.'}`,
      });
    } finally {
      setActionBusy(false);
    }
  };

  // Admin Live Fraud Decision right from the Live Sheet
  const handleAdminFraudDecision = async (alertId, decision) => {
    setActionBusy(true);
    setFeedback({ type: '', message: '' });
    try {
      const res =
        decision === 'APPROVE'
          ? await fraudAPI.approveFraudAlert(alertId, 'Approved live from Real-Time ACID Sheet')
          : await fraudAPI.rejectFraudAlert(alertId, 'Rejected live from Real-Time ACID Sheet');
      setFeedback({ type: 'success', message: `⚡ ${res.data.message}` });
      const snap = await liveSheetAPI.getSnapshot();
      applySnapshot(snap.data);
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to adjudicate alert.',
      });
    } finally {
      setActionBusy(false);
    }
  };

  const handleSyncOutbox = async () => {
    setActionBusy(true);
    try {
      const res = await auditAPI.triggerOutboxSync();
      setFeedback({ type: 'success', message: res.data.message });
      const snap = await liveSheetAPI.getSnapshot();
      applySnapshot(snap.data);
    } catch {
      setFeedback({ type: 'error', message: 'Outbox sync failed.' });
    } finally {
      setActionBusy(false);
    }
  };

  const sheetNames = useMemo(() => (snapshot?.sheets ? Object.keys(snapshot.sheets) : []), [snapshot]);
  const currentSheetData = snapshot?.sheets?.[activeSheet];

  const filteredRows = useMemo(() => {
    if (!currentSheetData) return [];
    if (!searchTerm.trim()) return currentSheetData.rows;
    const q = searchTerm.toLowerCase();
    return currentSheetData.rows.filter((row) =>
      currentSheetData.columns.some((col) => String(row[col] ?? '').toLowerCase().includes(q))
    );
  }, [currentSheetData, searchTerm]);

  const openFraudAlerts = useMemo(() => {
    if (!isAdmin || !snapshot?.sheets?.Fraud_Alerts) return [];
    return snapshot.sheets.Fraud_Alerts.rows.filter((r) => r.alert_status === 'OPEN');
  }, [isAdmin, snapshot]);

  if (!snapshot) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-9 h-9 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-semibold text-slate-600">Connecting to Real-Time PostgreSQL ACID Stream...</p>
      </div>
    );
  }

  const summary = snapshot.summary || {};

  return (
    <div className="space-y-4">
      {/* Excel-Style Green Title Ribbon */}
      <div className="bg-emerald-900 text-white rounded-2xl p-4 sm:p-5 shadow-md flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-700/80 border border-emerald-500/40 flex items-center justify-center flex-shrink-0">
            <FileSpreadsheet className="w-5 h-5 text-emerald-100" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg sm:text-xl font-bold tracking-tight">
                {isAdmin ? 'FinTrack_Live_Database.xlsx' : `FinTrack_${user?.username}_Live.xlsx`}
              </h1>
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                  connectionState === 'LIVE'
                    ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-400/40'
                    : connectionState === 'PAUSED'
                    ? 'bg-amber-500/20 text-amber-200 border border-amber-400/40'
                    : 'bg-sky-500/20 text-sky-200 border border-sky-400/40'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    connectionState === 'LIVE'
                      ? 'bg-emerald-400 animate-pulse'
                      : connectionState === 'PAUSED'
                      ? 'bg-amber-400'
                      : 'bg-sky-400 animate-pulse'
                  }`}
                />
                {connectionState === 'LIVE'
                  ? 'REAL-TIME SSE STREAM'
                  : connectionState === 'POLLING'
                  ? 'LIVE SYNC (1s)'
                  : connectionState === 'PAUSED'
                  ? 'PAUSED'
                  : 'CONNECTING'}
              </span>
            </div>
            <p className="text-xs text-emerald-100/80 mt-0.5">
              Live PostgreSQL 16 ACID Mirror • Auto-flashes changed cells &amp; double-entry ledger commits in real time
            </p>
          </div>
        </div>

        {/* Live ACID Double-Entry Balance Badge + Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {isAdmin && (
            <div
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold border ${
                summary.is_balanced
                  ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-200'
                  : 'bg-rose-950 border-rose-400 text-rose-200'
              }`}
            >
              DEBITS {formatCurrency(summary.total_debits)} = CREDITS {formatCurrency(summary.total_credits)}{' '}
              {summary.is_balanced ? '✓ BALANCED' : '✗ MISMATCH'}
            </div>
          )}

          <button
            onClick={handleTogglePause}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-800 hover:bg-emerald-700 text-xs font-semibold transition"
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            <span>{isPaused ? 'Resume' : 'Pause'}</span>
          </button>

          <button
            onClick={handleManualRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-800 hover:bg-emerald-700 text-xs font-semibold transition"
            title="Force refresh now"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleDownloadXlsx}
            disabled={downloading}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white text-emerald-900 hover:bg-emerald-50 text-xs font-bold shadow-sm transition disabled:opacity-60"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{downloading ? 'Saving...' : 'Download .xlsx'}</span>
          </button>
        </div>
      </div>

      {feedback.message && (
        <Alert
          type={feedback.type || 'info'}
          message={feedback.message}
          onClose={() => setFeedback({ type: '', message: '' })}
        />
      )}

      {/* Interactive Live ACID Trigger Bar */}
      {isCustomer && (
        <form
          onSubmit={handleRunAcidTransfer}
          className="bg-white rounded-2xl border border-slate-200 p-4 card-shadow space-y-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Live ACID Transfer Trigger — Watch Excel Cells Mutate in Real Time
              </h2>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => {
                  setTxAmount('500');
                  handleRunAcidTransfer(null, 500);
                }}
                className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition"
              >
                ⚡ Quick ₹500 ACID Commit
              </button>
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => {
                  setTxAmount('12000');
                  handleRunAcidTransfer(null, 12000);
                }}
                className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 transition"
              >
                🛡️ Quick ₹12,000 Hold (0 Balance Change)
              </button>
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => {
                  setTxAmount('999999');
                  handleRunAcidTransfer(null, 999999);
                }}
                className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition"
              >
                🚫 Test Overdraft Rollback
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
            <select
              value={txSender}
              onChange={(e) => setTxSender(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold"
            >
              {(snapshot.sheets.My_Accounts?.rows || []).map((acc) => (
                <option key={acc.account_id} value={acc.account_id}>
                  From #{acc.account_id} ({acc.account_type} • {formatCurrency(acc.balance)})
                </option>
              ))}
            </select>

            <input
              type="number"
              value={txReceiver}
              onChange={(e) => setTxReceiver(e.target.value)}
              placeholder="To Account ID (e.g. 1003)"
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold"
              required
            />

            <input
              type="number"
              step="0.01"
              value={txAmount}
              onChange={(e) => setTxAmount(e.target.value)}
              placeholder="Amount (INR)"
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-semibold"
              required
            />

            <input
              type="text"
              value={txDesc}
              onChange={(e) => setTxDesc(e.target.value)}
              placeholder="Description"
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
            />

            <button
              type="submit"
              disabled={actionBusy}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-bold shadow-sm transition disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{actionBusy ? 'Committing...' : 'Execute ACID'}</span>
            </button>
          </div>
        </form>
      )}

      {isAdmin && (
        <div className="bg-white rounded-2xl border border-slate-200 p-4 card-shadow flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs font-bold text-slate-800">
                Real-Time ACID Monitor ({summary.total_accounts} Accounts • {summary.total_transactions} Transfers •{' '}
                {summary.total_ledger_entries} Ledger Rows)
              </p>
              <p className="text-[11px] text-slate-500">
                Open a second browser tab logged in as <code className="bg-slate-100 px-1 rounded">arun_kumar</code> to
                send transfers and watch every table here flash live, or adjudicate an open compliance hold right now:
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {openFraudAlerts.length > 0 && (
              <>
                <button
                  onClick={() => handleAdminFraudDecision(openFraudAlerts[0].alert_id, 'APPROVE')}
                  disabled={actionBusy}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition disabled:opacity-50"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>
                    Approve Hold #{openFraudAlerts[0].alert_id} ({formatCurrency(openFraudAlerts[0].transfer_amount)})
                  </span>
                </button>
                <button
                  onClick={() => handleAdminFraudDecision(openFraudAlerts[0].alert_id, 'REJECT')}
                  disabled={actionBusy}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Reject #{openFraudAlerts[0].alert_id}</span>
                </button>
              </>
            )}

            <button
              onClick={handleSyncOutbox}
              disabled={actionBusy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition"
            >
              <Database className="w-3.5 h-3.5" />
              <span>Sync Outbox ({summary.pending_outbox || 0} pending)</span>
            </button>
          </div>
        </div>
      )}

      {/* Excel Container (Formula Bar + Grid + Bottom Worksheet Tabs) */}
      <div className="bg-white rounded-2xl border border-slate-300 shadow-sm overflow-hidden flex flex-col">
        {/* Excel Formula / Search Bar */}
        <div className="bg-slate-50 border-b border-slate-200 px-3 py-2 flex flex-col sm:flex-row sm:items-center gap-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <span className="px-2 py-1 rounded bg-white border border-slate-300 text-xs font-mono font-bold text-slate-700 min-w-[3.2rem] text-center">
              {selectedCell ? selectedCell.coord : 'A1'}
            </span>
            <span className="text-xs font-serif italic font-bold text-slate-400 px-1">fx</span>
            <div className="flex-1 bg-white border border-slate-300 rounded px-2.5 py-1 text-xs font-mono text-slate-700 truncate">
              {selectedCell
                ? `${activeSheet}!${selectedCell.coord} (${selectedCell.col}) = ${String(selectedCell.val ?? '')}`
                : acidLog.length > 0
                ? `⚡ [${acidLog[0].time}] ACID COMMIT: ${acidLog[0].summary}`
                : `=POSTGRESQL("fintrack", "${activeSheet}")  // Last sync ${new Date(snapshot.timestamp).toLocaleTimeString()}`}
            </div>
          </div>

          <div className="relative w-full sm:w-56">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={`Filter ${activeSheet}...`}
              className="w-full pl-8 pr-3 py-1 bg-white border border-slate-300 rounded text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Excel Spreadsheet Grid */}
        <div className="overflow-auto max-h-[56vh] bg-white">
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 z-10">
              {/* Row 0: Excel Letters A, B, C... */}
              <tr className="bg-slate-200 text-slate-600 font-bold text-[10px]">
                <th className="w-10 border border-slate-300 bg-slate-200 text-center py-1 sticky left-0 z-20">
                  #
                </th>
                {(currentSheetData?.columns || []).map((col, cIdx) => (
                  <th key={`letter-${col}`} className="border border-slate-300 px-2 py-1 text-center font-mono">
                    {colIndexToExcelLetter(cIdx)}
                  </th>
                ))}
              </tr>
              {/* Row 1: Column Names */}
              <tr className="bg-slate-900 text-white">
                <th className="w-10 border border-slate-700 bg-slate-800 text-center py-2 font-mono text-[10px] sticky left-0 z-20">
                  1
                </th>
                {(currentSheetData?.columns || []).map((col) => (
                  <th
                    key={col}
                    className="border border-slate-700 px-3 py-2 text-left font-semibold whitespace-nowrap tracking-wide"
                  >
                    {col.replace(/_/g, ' ').toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={(currentSheetData?.columns?.length || 1) + 1}
                    className="py-10 text-center text-slate-400 text-xs"
                  >
                    No rows matching filter in {activeSheet}.
                  </td>
                </tr>
              ) : (
                filteredRows.map((row, rIdx) => {
                  const keyField = currentSheetData.key_field;
                  const rowKey = String(row[keyField]);
                  const isNewRow = diffState.newRows[activeSheet]?.has(rowKey);

                  return (
                    <tr
                      key={rowKey}
                      className={`transition-colors duration-500 ${
                        isNewRow
                          ? 'bg-emerald-100/90'
                          : rIdx % 2 === 1
                          ? 'bg-slate-50/70 hover:bg-blue-50/40'
                          : 'bg-white hover:bg-blue-50/40'
                      }`}
                    >
                      {/* Sticky Row Number */}
                      <td
                        className={`border border-slate-200 text-center font-mono text-[11px] font-semibold py-1.5 sticky left-0 z-10 ${
                          isNewRow ? 'bg-emerald-200 text-emerald-900' : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {rIdx + 2}
                      </td>

                      {currentSheetData.columns.map((col, cIdx) => {
                        const val = row[col];
                        const coord = `${colIndexToExcelLetter(cIdx)}${rIdx + 2}`;
                        const cellDiff = diffState.changedCells[activeSheet]?.[`${rowKey}::${col}`];
                        const isCurrency = CURRENCY_COLS.has(col);
                        const isStatus = STATUS_COLS.has(col);
                        const isSelected = selectedCell?.coord === coord && selectedCell?.sheet === activeSheet;

                        let cellBg = '';
                        if (cellDiff) {
                          if (cellDiff.delta !== null && cellDiff.delta > 0) {
                            cellBg = 'bg-emerald-200 text-emerald-950 font-bold ring-2 ring-inset ring-emerald-500';
                          } else if (cellDiff.delta !== null && cellDiff.delta < 0) {
                            cellBg = 'bg-rose-200 text-rose-950 font-bold ring-2 ring-inset ring-rose-500';
                          } else {
                            cellBg = 'bg-amber-200 text-amber-950 font-bold ring-2 ring-inset ring-amber-500';
                          }
                        } else if (isSelected) {
                          cellBg = 'ring-2 ring-inset ring-emerald-600 bg-emerald-50/50';
                        }

                        return (
                          <td
                            key={col}
                            onClick={() => setSelectedCell({ sheet: activeSheet, coord, col, val })}
                            className={`border border-slate-200 px-3 py-1.5 whitespace-nowrap cursor-cell transition-all duration-500 ${
                              isCurrency ? 'text-right font-mono' : 'text-left'
                            } ${cellBg}`}
                          >
                            <div className={`flex items-center gap-1.5 ${isCurrency ? 'justify-end' : 'justify-start'}`}>
                              {cIdx === 0 && isNewRow && (
                                <span className="px-1.5 py-0.5 rounded bg-emerald-600 text-white text-[9px] font-bold uppercase tracking-wider animate-pulse">
                                  NEW
                                </span>
                              )}

                              {isStatus ? (
                                col === 'is_frozen' ? (
                                  <StatusBadge status={val ? 'FROZEN' : 'ACTIVE'} />
                                ) : (
                                  <StatusBadge status={String(val)} />
                                )
                              ) : isCurrency ? (
                                <span className="font-semibold text-slate-900">{formatCurrency(val)}</span>
                              ) : (
                                <span className="text-slate-700">{String(val ?? '')}</span>
                              )}

                              {cellDiff && cellDiff.delta !== null && cellDiff.delta !== 0 && (
                                <span
                                  className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                                    cellDiff.delta > 0
                                      ? 'bg-emerald-700 text-white'
                                      : 'bg-rose-700 text-white'
                                  }`}
                                >
                                  {cellDiff.delta > 0 ? '+' : ''}
                                  {formatCurrency(cellDiff.delta)}
                                </span>
                              )}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Classic Excel Bottom Worksheet Tabs */}
        <div className="bg-slate-100 border-t border-slate-300 px-2 pt-1.5 pb-1 flex items-center justify-between gap-2 overflow-x-auto">
          <div className="flex items-center gap-1">
            {sheetNames.map((name) => {
              const isActive = name === activeSheet;
              const badgeCount = diffState.sheetBadges[name] || 0;
              const rowCount = snapshot.sheets[name]?.rows?.length || 0;

              return (
                <button
                  key={name}
                  onClick={() => {
                    setActiveSheet(name);
                    setSelectedCell(null);
                  }}
                  className={`px-3 py-1.5 rounded-t-lg text-xs font-bold flex items-center gap-1.5 border-t border-x transition whitespace-nowrap ${
                    isActive
                      ? 'bg-white text-emerald-800 border-slate-300 shadow-sm -mb-1 pb-2'
                      : 'bg-slate-200/70 text-slate-600 border-transparent hover:bg-slate-200'
                  }`}
                >
                  <span>{name}</span>
                  <span className="text-[10px] font-mono text-slate-400">({rowCount})</span>
                  {badgeCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full bg-emerald-600 text-white text-[10px] font-bold animate-bounce">
                      +{badgeCount}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="text-[11px] font-mono text-slate-500 px-2 whitespace-nowrap hidden lg:block">
            Rows: {filteredRows.length} | Sync: {new Date(snapshot.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* Live ACID Commit Activity Log */}
      {acidLog.length > 0 && (
        <div className="bg-slate-900 text-slate-100 rounded-2xl p-4 border border-slate-800">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-300">
              Live ACID Transaction Commit Stream
            </h3>
          </div>
          <div className="space-y-1 font-mono text-xs">
            {acidLog.map((evt) => (
              <div key={evt.id} className="flex items-start gap-2 text-slate-300">
                <span className="text-emerald-400 flex-shrink-0">[{evt.time}]</span>
                <span>⚡ {evt.summary}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveExcelSheet;

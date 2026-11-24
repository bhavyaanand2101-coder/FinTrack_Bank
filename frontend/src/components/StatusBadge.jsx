import React from 'react';

const StatusBadge = ({ status }) => {
  const norm = (status || '').toUpperCase();

  const config = {
    SUCCESS: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'Success' },
    APPROVED: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'Approved' },
    ACTIVE: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'Active' },
    'PRE-APPROVED': { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'Pre-Approved' },
    ELIGIBLE: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', label: 'Eligible' },
    PENDING: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', label: 'Pending' },
    OPEN: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', label: 'Open Review' },
    FLAGGED: { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-300', label: 'Flagged Hold' },
    FAILED: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200', label: 'Failed' },
    REJECTED: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200', label: 'Rejected' },
    FROZEN: { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-300', label: 'Frozen' },
    DEBIT: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200', label: 'Debit' },
    CREDIT: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'Credit' },
  };

  const style = config[norm] || {
    bg: 'bg-slate-100',
    text: 'text-slate-700',
    border: 'border-slate-200',
    label: status || 'Unknown',
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${style.bg} ${style.text} ${style.border}`}
    >
      {style.label}
    </span>
  );
};

export default StatusBadge;


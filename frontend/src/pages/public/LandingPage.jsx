import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, Database, Lock, ArrowLeftRight, FileText, CheckCircle2 } from 'lucide-react';

const LandingPage = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-accent border border-blue-200 mb-4">
          Full-Stack Relational Database Management System
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
          Smart Digital Banking & <span className="text-accent">Loan Management</span>
        </h1>
        <p className="mt-4 text-base sm:text-lg text-slate-600 leading-relaxed">
          FinTrack is an enterprise-grade banking application built on PostgreSQL 16 ACID transactions,
          double-entry ledger accounting, deterministic fraud controls, and transactional MongoDB audit outbox.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/login"
            className="w-full sm:w-auto px-6 py-3 text-sm font-bold text-white bg-accent hover:bg-accent-hover rounded-xl shadow-md transition"
          >
            Access Portal
          </Link>
          <Link
            to="/register"
            className="w-full sm:w-auto px-6 py-3 text-sm font-bold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-xl transition"
          >
            Create New Account
          </Link>
        </div>
      </div>

      {/* Core Architectural Pillars */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-accent flex items-center justify-center mb-4">
            <Lock className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Deterministic ACID Concurrency</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Eliminates deadlock potential across concurrent transfers using deterministic ascending row locks
            (<code className="bg-slate-100 text-xs px-1 py-0.5 rounded">SELECT FOR UPDATE ORDER BY account_id ASC</code>).
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
            <Database className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Double-Entry Ledger Integrity</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Every successful transfer produces two strictly balanced ledger entries (1 Debit, 1 Credit). Immutable database triggers prohibit manual manipulation.
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-4">
            <Shield className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Deterministic Fraud Holds</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Transfers $\ge$ ₹10,000 are automatically flagged for manual review with zero fund movement until administrative approval.
          </p>
        </div>
      </div>

      {/* Demo Credentials Quick Reference */}
      <div className="bg-white rounded-2xl border border-slate-200 p-8 card-shadow max-w-4xl mx-auto">
        <h3 className="text-xl font-bold text-slate-900 mb-2 text-center">Demonstration Credentials</h3>
        <p className="text-xs text-slate-500 text-center mb-6">
          Pre-seeded test accounts for presentation and grading:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-xs font-bold uppercase tracking-wider text-accent">Administrator</span>
            <p className="text-sm font-bold text-slate-900 mt-1">admin</p>
            <p className="text-xs text-slate-600">Password: <code className="bg-slate-200 px-1 py-0.5 rounded">AdminPassword123!</code></p>
            <p className="text-[11px] text-slate-500 mt-2">Full admin controls & audit logs</p>
          </div>

          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-600">Customer 1</span>
            <p className="text-sm font-bold text-slate-900 mt-1">arun_kumar</p>
            <p className="text-xs text-slate-600">Password: <code className="bg-slate-200 px-1 py-0.5 rounded">Customer123!</code></p>
            <p className="text-[11px] text-slate-500 mt-2">Accounts 1001 & 1002 (Active)</p>
          </div>

          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600">Customer 2</span>
            <p className="text-sm font-bold text-slate-900 mt-1">priya_sharma</p>
            <p className="text-xs text-slate-600">Password: <code className="bg-slate-200 px-1 py-0.5 rounded">Customer123!</code></p>
            <p className="text-[11px] text-slate-500 mt-2">High credit score (810, Loan Eligible)</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;


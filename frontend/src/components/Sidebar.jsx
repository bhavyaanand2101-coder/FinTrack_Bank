import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  History,
  FileText,
  User,
  Users,
  ShieldAlert,
  Lock,
  BarChart3,
  CheckSquare,
  FileSpreadsheet,
} from 'lucide-react';

const Sidebar = () => {
  const { user, isCustomer, isAdmin } = useAuth();

  if (!user) return null;

  const customerLinks = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/accounts', label: 'My Accounts', icon: Wallet },
    { to: '/transfers', label: 'Transfer Money', icon: ArrowLeftRight },
    { to: '/transactions', label: 'Transactions', icon: History },
    { to: '/loans', label: 'Loans & Credit', icon: FileText },
    { to: '/live-sheet', label: 'Live Excel Sheet', icon: FileSpreadsheet, live: true },
    { to: '/profile', label: 'My Profile', icon: User },
  ];

  const adminLinks = [
    { to: '/admin', label: 'Overview', icon: LayoutDashboard },
    { to: '/admin/live-sheet', label: 'Live Excel Sheet', icon: FileSpreadsheet, live: true },
    { to: '/admin/customers', label: 'Customer Accounts', icon: Users },
    { to: '/admin/loans', label: 'Loan Approvals', icon: CheckSquare },
    { to: '/admin/fraud', label: 'Fraud Reviews', icon: ShieldAlert },
    { to: '/admin/audit', label: 'Security Audit Logs', icon: Lock },
    { to: '/admin/reports', label: 'Advanced Reports', icon: BarChart3 },
  ];

  const links = isAdmin ? adminLinks : customerLinks;

  return (
    <aside className="w-64 bg-white border-r border-slate-200 min-h-[calc(100vh-4rem)] p-4 flex flex-col justify-between hidden md:flex">
      <div>
        <div className="px-3 py-2 mb-2">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
            {isAdmin ? 'Administration Portal' : 'Banking Menu'}
          </p>
        </div>

        <nav className="space-y-1">
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/admin' || link.to === '/dashboard'}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition ${
                    isActive
                      ? 'bg-blue-50 text-accent'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1">{link.label}</span>
                {link.live && (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[9px] font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    LIVE
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
        <p className="text-xs font-semibold text-slate-700">Database Engine</p>
        <p className="text-[11px] text-slate-500 mt-0.5">PostgreSQL 16 + ACID Locks</p>
        <p className="text-[11px] text-slate-500">Append-only MongoDB Audit</p>
      </div>
    </aside>
  );
};

export default Sidebar;


import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { systemAPI } from '../api/client';
import { Shield, User, LogOut, CheckCircle2, AlertCircle } from 'lucide-react';

const Navbar = () => {
  const { user, logout, isCustomer, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [health, setHealth] = useState({ pg: true, mongo: true });

  useEffect(() => {
    systemAPI
      .getHealth()
      .then((res) => {
        setHealth({
          pg: res.data.databases.postgresql === 'ONLINE',
          mongo: res.data.databases.mongodb === 'ONLINE',
        });
      })
      .catch(() => {
        setHealth({ pg: false, mongo: false });
      });
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 card-shadow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <Link to="/" className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-primary to-accent flex items-center justify-center shadow-md">
              <span className="text-white font-bold text-lg">F</span>
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-slate-900">FinTrack</span>
              <span className="hidden sm:inline-block text-xs font-semibold px-2 py-0.5 ml-2 rounded bg-slate-100 text-slate-600">
                DBMS v2.0
              </span>
            </div>
          </Link>
        </div>

        {/* Status Indicators & User Profile */}
        <div className="flex items-center space-x-4">
          {/* Database Health Pills */}
          <div className="hidden md:flex items-center space-x-2 text-xs">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-md font-medium ${
                health.pg ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${health.pg ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              PostgreSQL
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-md font-medium ${
                health.mongo ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${health.mongo ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              MongoDB
            </span>
          </div>

          {user ? (
            <div className="flex items-center space-x-3 pl-3 border-l border-slate-200">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-semibold text-slate-900 leading-tight">
                  {user.full_name || user.username}
                </p>
                <p className="text-xs text-slate-500">
                  {isAdmin ? '🛡️ Administrator' : `Customer #${user.customer_id}`}
                </p>
              </div>

              <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 font-bold text-sm">
                {user.username.charAt(0).toUpperCase()}
              </div>

              <button
                onClick={handleLogout}
                title="Log out"
                className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <Link
                to="/login"
                className="px-3.5 py-1.5 text-sm font-semibold text-slate-700 hover:text-slate-900 transition"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="px-3.5 py-1.5 text-sm font-semibold text-white bg-accent hover:bg-accent-hover rounded-lg transition shadow-sm"
              >
                Open Account
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;


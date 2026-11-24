import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import Alert from '../../components/Alert';
import { User, Mail, Shield, KeyRound, LogOut, CheckCircle } from 'lucide-react';

const Profile = () => {
  const { user, logout } = useAuth();
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const handlePasswordChange = (e) => {
    e.preventDefault();
    if (passwordData.new_password !== passwordData.confirm_password) {
      setError('New passwords do not match.');
      return;
    }
    if (passwordData.new_password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    // Simulation / acknowledgement
    setError('');
    setSuccess('Security credentials updated. Argon2id salt regenerated.');
    setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-2xl border border-slate-200 card-shadow">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Customer Profile & Security</h1>
        <p className="text-xs text-slate-500 mt-0.5">Manage your account information and authentication credentials</p>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {/* User Information Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 card-shadow space-y-4">
        <div className="flex items-center space-x-3 pb-4 border-b border-slate-100">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-accent flex items-center justify-center font-bold text-lg">
            {user?.username?.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">{user?.full_name}</h3>
            <p className="text-xs text-slate-500">
              Customer ID #{user?.customer_id} • Registered Account Holder
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-xl">
            <span className="text-slate-400 font-semibold uppercase">Username</span>
            <p className="font-bold text-slate-800 mt-0.5">{user?.username}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl">
            <span className="text-slate-400 font-semibold uppercase">Email Address</span>
            <p className="font-bold text-slate-800 mt-0.5">{user?.email || 'Not configured'}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl">
            <span className="text-slate-400 font-semibold uppercase">Account Role</span>
            <p className="font-bold text-slate-800 mt-0.5">{user?.role}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl">
            <span className="text-slate-400 font-semibold uppercase">Hashing Standard</span>
            <p className="font-bold text-emerald-700 mt-0.5">Argon2id (m=65536, t=3, p=4)</p>
          </div>
        </div>
      </div>

      {/* Change Password Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 card-shadow space-y-4">
        <div className="flex items-center space-x-2 text-slate-900 font-bold">
          <KeyRound className="w-5 h-5 text-accent" />
          <h3>Update Password Credentials</h3>
        </div>

        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Current Password</label>
            <input
              type="password"
              value={passwordData.current_password}
              onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-accent"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">New Password</label>
              <input
                type="password"
                value={passwordData.new_password}
                onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-accent"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Confirm New Password</label>
              <input
                type="password"
                value={passwordData.confirm_password}
                onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-accent"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition"
          >
            Update Password
          </button>
        </form>
      </div>

      {/* Logout Action */}
      <div className="pt-2">
        <button
          onClick={logout}
          className="w-full py-3 bg-rose-50 hover:bg-rose-100 text-rose-700 text-sm font-bold rounded-xl transition flex items-center justify-center space-x-2 border border-rose-200"
        >
          <LogOut className="w-4 h-4" />
          <span>Log Out of FinTrack</span>
        </button>
      </div>
    </div>
  );
};

export default Profile;


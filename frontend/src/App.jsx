import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';

// Public Pages
import LandingPage from './pages/public/LandingPage';
import LoginPage from './pages/public/LoginPage';
import RegisterPage from './pages/public/RegisterPage';

// Customer Pages
import CustomerDashboard from './pages/customer/CustomerDashboard';
import MyAccounts from './pages/customer/MyAccounts';
import TransferMoney from './pages/customer/TransferMoney';
import Transactions from './pages/customer/Transactions';
import Loans from './pages/customer/Loans';
import Profile from './pages/customer/Profile';

// Admin Pages
import AdminDashboard from './pages/admin/AdminDashboard';
import CustomerManagement from './pages/admin/CustomerManagement';
import LoanManagement from './pages/admin/LoanManagement';
import FraudManagement from './pages/admin/FraudManagement';
import AuditLogs from './pages/admin/AuditLogs';
import Reports from './pages/admin/Reports';
import LiveExcelSheet from './pages/LiveExcelSheet';

// Layout Component
const AppLayout = () => {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />
      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        {isAuthenticated && <Sidebar />}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

// Protected Customer Route
const CustomerRoute = () => {
  const { user, loading, isCustomer } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!isCustomer) return <Navigate to="/admin" replace />;
  return <Outlet />;
};

// Protected Admin Route
const AdminRoute = () => {
  const { user, loading, isAdmin } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
};

// Public Only Route (Redirects away if already signed in)
const PublicOnlyRoute = () => {
  const { user, loading, isAdmin } = useAuth();
  if (loading) return null;
  if (user) {
    return <Navigate to={isAdmin ? '/admin' : '/dashboard'} replace />;
  }
  return <Outlet />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            {/* Public Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>

            {/* Customer Routes */}
            <Route element={<CustomerRoute />}>
              <Route path="/dashboard" element={<CustomerDashboard />} />
              <Route path="/accounts" element={<MyAccounts />} />
              <Route path="/transfers" element={<TransferMoney />} />
              <Route path="/transactions" element={<Transactions />} />
              <Route path="/loans" element={<Loans />} />
              <Route path="/live-sheet" element={<LiveExcelSheet />} />
              <Route path="/profile" element={<Profile />} />
            </Route>

            {/* Admin Routes */}
            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="/admin/live-sheet" element={<LiveExcelSheet />} />
              <Route path="/admin/customers" element={<CustomerManagement />} />
              <Route path="/admin/loans" element={<LoanManagement />} />
              <Route path="/admin/fraud" element={<FraudManagement />} />
              <Route path="/admin/audit" element={<AuditLogs />} />
              <Route path="/admin/reports" element={<Reports />} />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;


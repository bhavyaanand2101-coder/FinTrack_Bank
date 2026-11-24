import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('fintrack_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle session expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token and trigger logout if not already on login page
      localStorage.removeItem('fintrack_token');
      localStorage.removeItem('fintrack_user');
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register' && window.location.pathname !== '/') {
        window.location.href = '/login?expired=true';
      }
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

export const authAPI = {
  login: (credentials) => api.post('/auth/login', credentials),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
};

export const accountsAPI = {
  getAccounts: () => api.get('/accounts'),
  getAccountDetail: (id) => api.get(`/accounts/${id}`),
  getAccountBalance: (id) => api.get(`/accounts/${id}/balance`),
  getAccountSummary: (id) => api.get(`/accounts/${id}/summary`),
  getAccountStatement: (id, limit = 20) => api.get(`/accounts/${id}/statement?limit=${limit}`),
  downloadMyExcel: () => api.get('/accounts/export-excel', { responseType: 'blob' }),
};

export const transfersAPI = {
  executeTransfer: (payload) => api.post('/transfers', payload),
  getTransactions: (params = {}) => api.get('/transfers', { params }),
  getTransactionById: (id) => api.get(`/transfers/${id}`),
  lookupRecipient: (accNo) => api.get(`/transfers/recipient/${accNo}`),
};

export const loansAPI = {
  calculateEligibility: (data) => api.post('/loans/calculate', data),
  applyForLoan: (data) => api.post('/loans', data),
  getCustomerLoans: () => api.get('/loans'),
  getAdminLoans: (statusFilter) => api.get('/admin/loans', { params: { status_filter: statusFilter } }),
  approveLoan: (id) => api.patch(`/admin/loans/${id}/approve`),
  rejectLoan: (id) => api.patch(`/admin/loans/${id}/reject`),
};

export const adminAPI = {
  getDashboardKPIs: () => api.get('/admin/dashboard'),
  getCustomers: (search) => api.get('/admin/customers', { params: { search } }),
  toggleAccountFreeze: (accountId, freeze) => api.patch(`/admin/accounts/${accountId}/freeze`, { freeze }),
  getAllTransactions: (params = {}) => api.get('/admin/transactions', { params }),
  getAdvancedReports: () => api.get('/admin/reports'),
  getExcelStatus: () => api.get('/admin/excel-status'),
  downloadExcel: () => api.get('/admin/export-excel', { responseType: 'blob' }),
};

export const fraudAPI = {
  getFraudAlerts: (statusFilter) => api.get('/admin/fraud-alerts', { params: { status_filter: statusFilter } }),
  approveFraudAlert: (id, notes = '') => api.patch(`/admin/fraud-alerts/${id}/approve`, { decision: 'APPROVE', notes }),
  rejectFraudAlert: (id, notes = '') => api.patch(`/admin/fraud-alerts/${id}/reject`, { decision: 'REJECT', notes }),
};

export const auditAPI = {
  getAuditLogs: (params = {}) => api.get('/admin/audit-logs', { params }),
  getAuditLogById: (id) => api.get(`/admin/audit-logs/${id}`),
  triggerOutboxSync: () => api.post('/admin/audit-logs/sync'),
};

export const systemAPI = {
  getHealth: () => api.get('/health'),
};

export const liveSheetAPI = {
  getSnapshot: (sinceFingerprint = null) =>
    api.get('/live-sheet/snapshot', {
      params: sinceFingerprint ? { since_fingerprint: sinceFingerprint } : {},
    }),
  getStreamUrl: (token) => `${API_BASE_URL}/live-sheet/stream?token=${encodeURIComponent(token)}`,
};

export default api;


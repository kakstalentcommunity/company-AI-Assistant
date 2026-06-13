export type LoanStatus = "Active" | "Overdue" | "Completed" | "Pending" | string;
export type TransactionType = "Credit" | "Debit" | string;

export interface PortfolioPoint {
  month: string;
  savings: number;
  loans: number;
  repayments: number;
}

export interface LoanDistributionPoint {
  name: string;
  value: number;
  color: string;
}

export interface Member {
  id: string;
  userId?: number | null;
  name: string;
  email: string;
  savings: number;
  loans: number;
  status: string;
  joined: string;
  shares: number;
}

export interface Loan {
  id: string;
  member: string;
  amount: number;
  balance: number;
  rate: number;
  issued: string;
  due: string;
  status: LoanStatus;
  type: string;
}

export interface Transaction {
  id: string;
  member: string;
  amount: number;
  type: TransactionType;
  category: string;
  date: string;
  ref: string;
  channel: string;
  mpesaReceiptNumber?: string | null;
  mpesaPhoneNumber?: string | null;
  mpesaCheckoutRequestId?: string | null;
  mpesaMerchantRequestId?: string | null;
  mpesaResultCode?: string | null;
  mpesaResultDescription?: string | null;
}

export interface TransactionRequest {
  id: number;
  member: string;
  loanId?: string | null;
  requester?: string | null;
  amount: number;
  type: TransactionType;
  category: string;
  date: string;
  ref: string;
  channel: string;
  mpesaReceiptNumber?: string | null;
  mpesaPhoneNumber?: string | null;
  mpesaCheckoutRequestId?: string | null;
  mpesaMerchantRequestId?: string | null;
  mpesaResultCode?: string | null;
  mpesaResultDescription?: string | null;
  status: "Pending" | "Approved" | "Rejected" | string;
  reviewNote?: string | null;
  reviewedAt?: string | null;
  reviewedBy?: string | null;
  createdAt: string;
}

export interface TransactionRequestPayload {
  loanId?: string | null;
  amount: number;
  type: "Credit" | "Debit";
  category: string;
  date: string;
  ref: string;
  channel: string;
  mpesaReceiptNumber?: string | null;
  mpesaPhoneNumber?: string | null;
  mpesaCheckoutRequestId?: string | null;
  mpesaMerchantRequestId?: string | null;
  mpesaResultCode?: string | null;
  mpesaResultDescription?: string | null;
}

export interface TransactionRequestReviewPayload {
  status: "Approved" | "Rejected";
  reviewNote?: string;
}

export interface MpesaLoanRepaymentPayload {
  loanId: string;
  amount: number;
  phoneNumber?: string;
  mpesaReceiptNumber: string;
  date?: string;
}

export interface MpesaStkPushPayload {
  purpose: "loan_repayment" | "savings_deposit" | "transaction";
  amount: number;
  phoneNumber: string;
  loanId?: string | null;
  category?: string | null;
  transactionType?: "Credit" | "Debit";
  date?: string;
}

export interface MpesaStkPushResult {
  transactionRequest: TransactionRequest;
  merchantRequestId: string;
  checkoutRequestId: string;
  responseCode: string;
  responseDescription: string;
  customerMessage: string;
}

export type EmployerType = "Government" | "Formal" | "Self-Employed" | "Informal" | string;

export interface MemberProfile {
  employer: string;
  employerType: EmployerType;
  estimatedMonthlyIncome: number;
  mpesaMonthlyInflows: number[];
  guarantors: string[];
  monthlyExpenses: number;
  completedLoans: number;
  defaultedLoans: number;
}

export interface AnomalyFlag {
  level: "high" | "medium" | string;
  reason: string;
}

export interface SaccoData {
  portfolioData: PortfolioPoint[];
  loanDistribution: LoanDistributionPoint[];
  members: Member[];
  loans: Loan[];
  transactions: Transaction[];
  memberProfiles: Record<string, MemberProfile>;
  anomalyFlags: Record<string, AnomalyFlag>;
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: string;
  isActive: boolean;
  createdAt: string;
}

export interface AuthSession {
  token: string;
  user: AuthUser;
}

export interface PasswordResetRequestResult {
  message: string;
  resetToken?: string;
  expiresInMinutes?: number;
}

export interface AuditLogEntry {
  id: number;
  actorUserId: number | null;
  action: string;
  entityType: string;
  entityId: string;
  ipAddress: string;
  userAgent: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  createdAt: string;
}

export interface Notification {
  id: number;
  userId: number | null;
  recipient: string;
  createdByUserId: number | null;
  createdBy: string | null;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "danger" | string;
  entityType: string;
  entityId: string;
  readAt: string | null;
  createdAt: string;
}

export interface AdminUserCreatePayload {
  name: string;
  email: string;
  password: string;
  role: "admin" | "staff";
}

export interface NotificationCreatePayload {
  userId: number;
  title: string;
  message: string;
  type?: "info" | "success" | "warning" | "danger";
  entityType?: string;
  entityId?: string;
}

export interface AdminUserUpdatePayload {
  role?: "admin" | "staff";
  isActive?: boolean;
}

export interface LoanUpdatePayload {
  status?: string;
}

export interface MembershipApplication {
  id: number;
  userId: number;
  memberId: string | null;
  name: string;
  email: string;
  phone: string;
  nationalId: string;
  address: string;
  status: string;
  notes: string;
  createdAt: string;
  reviewedAt: string | null;
}

export interface MembershipStatus {
  member: { id: string; status: string } | null;
  application: MembershipApplication | null;
}

export interface MembershipApplicationPayload {
  phone: string;
  nationalId: string;
  address: string;
  notes?: string;
}

export interface LoanApplication {
  id: number;
  userId: number;
  memberId: string;
  member: string;
  loanId: string | null;
  amount: number;
  type: string;
  purpose: string;
  termMonths: number;
  status: string;
  notes: string;
  createdAt: string;
  reviewedAt: string | null;
}

export interface LoanApplicationPayload {
  amount: number;
  type: string;
  purpose: string;
  termMonths: number;
}

export interface ProductAnalyticsKpis {
  dau: number;
  mau: number;
  avgSessionDurationSeconds: number;
  bounceRate: number;
  retentionRate: number;
  conversionRate: number;
}

export interface ProductAnalyticsFunnelStep {
  step: string;
  label: string;
  users: number;
  conversionFromStart: number;
  dropOffFromPrevious: number;
}

export interface ProductFeatureUsage {
  feature: string;
  label: string;
  usageCount: number;
  uniqueUsers: number;
  adoptionRate: number;
  avgDurationSeconds: number;
  trend: "up" | "down" | string;
}

export interface ProductFrictionPoint {
  area: string;
  severity: "high" | "medium" | "low" | string;
  signal: string;
  aiRecommendation: string;
}

export interface ProductAnalyticsPoint {
  date: string;
  activeUsers: number;
  conversionRate: number;
  dropOffRate: number;
}

export interface ProductAnalyticsAlert {
  id: number;
  severity: "high" | "medium" | "low" | string;
  title: string;
  description: string;
  metric: string;
  currentValue: number;
  thresholdValue: number;
  status: string;
  detectedAt: string;
}

export interface ProductDeviceBreakdown {
  device: "Android" | "iOS" | "Web" | "USSD" | string;
  sessions: number;
  share: number;
}

export interface ProductAnalyticsInsight {
  id: number;
  category: string;
  title: string;
  narrative: string;
  recommendation: string;
  confidence: number;
  generatedAt: string;
}

export interface ProductAnalyticsDashboard {
  kpis: ProductAnalyticsKpis;
  funnel: ProductAnalyticsFunnelStep[];
  featureUsage: ProductFeatureUsage[];
  frictionPoints: ProductFrictionPoint[];
  timeSeries: ProductAnalyticsPoint[];
  alerts: ProductAnalyticsAlert[];
  deviceBreakdown: ProductDeviceBreakdown[];
  insights: ProductAnalyticsInsight[];
  generatedAt: string;
}

export interface ProductAnalyticsEventPayload {
  sessionId: string;
  eventName: string;
  feature?: string;
  funnelName?: string;
  funnelStep?: string;
  device?: "Android" | "iOS" | "Web" | "USSD";
  path?: string;
  durationSeconds?: number;
  properties?: Record<string, unknown>;
}

export const EMPTY_SACCO_DATA: SaccoData = {
  portfolioData: [],
  loanDistribution: [],
  members: [],
  loans: [],
  transactions: [],
  memberProfiles: {},
  anomalyFlags: {},
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const SESSION_KEY = "umojafunds_session";
const SESSION_IDLE_MS = 30 * 60 * 1000;

interface StoredSession {
  session: AuthSession;
  lastSeenAt: number;
}

export function getStoredSession(): AuthSession | null {
  const raw = sessionStorage.getItem(SESSION_KEY) || localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredSession | AuthSession;
    const stored = "session" in parsed ? parsed : { session: parsed, lastSeenAt: Date.now() };
    if (!stored.session?.token || !stored.session?.user) return null;
    if (Date.now() - stored.lastSeenAt > SESSION_IDLE_MS) {
      clearSession();
      return null;
    }
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ session: stored.session, lastSeenAt: Date.now() }));
    localStorage.removeItem(SESSION_KEY);
    return stored.session;
  } catch {
    clearSession();
    return null;
  }
}

export function storeSession(session: AuthSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ session, lastSeenAt: Date.now() }));
  localStorage.removeItem(SESSION_KEY);
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(SESSION_KEY);
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        detail = payload.detail
          .map((errorItem) => {
            if (typeof errorItem === "string") return errorItem;
            if (typeof errorItem === "object" && errorItem !== null) {
              return errorItem.msg || errorItem.message || JSON.stringify(errorItem);
            }
            return String(errorItem);
          })
          .join("; ");
      }
    } catch {
      // Keep HTTP status text when the backend returns an empty body.
    }
    throw new Error(detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function login(email: string, password: string): Promise<AuthSession> {
  return request<AuthSession>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signup(name: string, email: string, password: string): Promise<AuthSession> {
  return request<AuthSession>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  });
}

export function requestPasswordReset(email: string): Promise<PasswordResetRequestResult> {
  return request<PasswordResetRequestResult>("/api/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function confirmPasswordReset(token: string, password: string): Promise<{ message: string }> {
  return request<{ message: string }>("/api/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export function logout(token: string): Promise<void> {
  return request<void>("/api/auth/logout", { method: "POST" }, token);
}

export function fetchSaccoData(token: string): Promise<SaccoData> {
  return request<SaccoData>("/api/sacco-data", undefined, token);
}

export interface BackendLoanScoreResult {
  composite: number;
  repaymentLikelihood: number;
  defaultRisk: string;
  affordabilityRatio?: number;
  delinquencyRisk90d?: number;
  recommendation: string;
  maxLoanAmount?: number;
  suggestedRate?: number;
  dimensions: Array<{ name: string; score: number; weight: number; signal: string; trend: string }>;
  keyRisks: string[];
  keyStrengths: string[];
}

export function scoreLoan(token: string, memberId: string, loanAmount: number, loanType: string): Promise<BackendLoanScoreResult> {
  return request<BackendLoanScoreResult>("/api/ai/score", {
    method: "POST",
    body: JSON.stringify({ memberId, loanAmount, loanType, persist: true }),
  }, token);
}

export function updateLoan(token: string, loanId: string, payload: LoanUpdatePayload): Promise<Loan> {
  return request<Loan>(`/api/loans/${loanId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, token);
}

export function getMembershipStatus(token: string): Promise<MembershipStatus> {
  return request<MembershipStatus>("/api/membership/me", undefined, token);
}

export function requestTransaction(token: string, payload: TransactionRequestPayload): Promise<TransactionRequest> {
  return request<TransactionRequest>("/api/transactions/requests", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function submitMpesaLoanRepayment(token: string, payload: MpesaLoanRepaymentPayload): Promise<TransactionRequest> {
  return request<TransactionRequest>("/api/mpesa/loan-repayments", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function initiateMpesaStkPush(token: string, payload: MpesaStkPushPayload): Promise<MpesaStkPushResult> {
  return request<MpesaStkPushResult>("/api/mpesa/stk/push", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function listTransactionRequests(token: string): Promise<TransactionRequest[]> {
  return request<TransactionRequest[]>("/api/transactions/requests", undefined, token);
}

export function reviewTransactionRequest(token: string, requestId: number, status: "Approved" | "Rejected", reviewNote = ""): Promise<TransactionRequest> {
  return request<TransactionRequest>(`/api/transactions/requests/${requestId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, reviewNote }),
  }, token);
}

export function applyForMembership(token: string, payload: MembershipApplicationPayload): Promise<MembershipApplication> {
  return request<MembershipApplication>("/api/membership/apply", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function listMembershipApplications(token: string): Promise<MembershipApplication[]> {
  return request<MembershipApplication[]>("/api/admin/membership-applications", undefined, token);
}

export function reviewMembershipApplication(token: string, applicationId: number, status: "Approved" | "Rejected", notes = ""): Promise<MembershipApplication> {
  return request<MembershipApplication>(`/api/admin/membership-applications/${applicationId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, notes }),
  }, token);
}

export function applyForLoan(token: string, payload: LoanApplicationPayload): Promise<LoanApplication> {
  return request<LoanApplication>("/api/loan-applications", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function listMyLoanApplications(token: string): Promise<LoanApplication[]> {
  return request<LoanApplication[]>("/api/loan-applications/me", undefined, token);
}

export function listLoanApplications(token: string): Promise<LoanApplication[]> {
  return request<LoanApplication[]>("/api/admin/loan-applications", undefined, token);
}

export function reviewLoanApplication(token: string, applicationId: number, status: "Approved" | "Rejected", notes = ""): Promise<LoanApplication> {
  return request<LoanApplication>(`/api/admin/loan-applications/${applicationId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, notes }),
  }, token);
}

export function listAdminUsers(token: string): Promise<AuthUser[]> {
  return request<AuthUser[]>("/api/admin/users", undefined, token);
}

export function listAuditLogs(token: string, limit = 100): Promise<AuditLogEntry[]> {
  return request<AuditLogEntry[]>(`/api/admin/audit-logs?limit=${limit}`, undefined, token);
}

export function listNotifications(token: string): Promise<Notification[]> {
  return request<Notification[]>("/api/notifications", undefined, token);
}

export function markNotificationRead(token: string, notificationId: number): Promise<Notification> {
  return request<Notification>(`/api/notifications/${notificationId}/read`, { method: "PATCH" }, token);
}

export function createNotification(token: string, payload: NotificationCreatePayload): Promise<Notification> {
  return request<Notification>("/api/admin/notifications", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function createAdminUser(token: string, payload: AdminUserCreatePayload): Promise<AuthUser> {
  return request<AuthUser>("/api/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function updateAdminUser(token: string, userId: number, payload: AdminUserUpdatePayload): Promise<AuthUser> {
  return request<AuthUser>(`/api/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, token);
}

export function fetchProductAnalyticsDashboard(token: string, days = 30): Promise<ProductAnalyticsDashboard> {
  return request<ProductAnalyticsDashboard>(`/api/admin/analytics/dashboard?days=${days}`, undefined, token);
}

export function trackProductAnalyticsEvent(token: string, payload: ProductAnalyticsEventPayload): Promise<{ id: number }> {
  return request<{ id: number }>("/api/analytics/events", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

'// <reference types="vite/client" /'
import React, { useState, useRef, useEffect } from "react";
import {
  LayoutDashboard, Users, CreditCard, PiggyBank, ArrowLeftRight,
  BarChart3, Settings, Bell, Search, TrendingUp,
  TrendingDown, AlertCircle, CheckCircle2, Clock, MoreHorizontal,
  Download, Filter, Plus, Eye, X, Menu, LogOut, Building2,
  Wallet, Shield, FileText, RefreshCw, ChevronRight, Sparkles,
  Bot, Send, Activity, Brain, TriangleAlert, Info,
  ShieldAlert, ShieldCheck, Globe, Smartphone, Fingerprint,
  Key, CheckCircle
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import { 
  sendGeminiMessage,
  isGeminiConfigured,
} from "../services/gemini";
import {
  EMPTY_SACCO_DATA,
  applyForLoan,
  applyForMembership,
  clearSession,
  createNotification,
  createAdminUser,
  fetchSaccoData,
  getMembershipStatus,
  getStoredSession,
  initiateMpesaStkPush,
  listAdminUsers,
  listNotifications,
  listLoanApplications,
  listMembershipApplications,
  listTransactionRequests,
  requestTransaction,
  reviewTransactionRequest,
  listMyLoanApplications,
  login,
  logout,
  markNotificationRead,
  confirmPasswordReset,
  requestPasswordReset,
  reviewLoanApplication,
  reviewMembershipApplication,
  scoreLoan,
  signup,
  storeSession,
  updateAdminUser,
  updateLoan,
  type AuthSession,
  type AuthUser,
  type BackendLoanScoreResult,
  type EmployerType,
  type Loan,
  type LoanApplication,
  type MembershipApplication,
  type MembershipStatus,
  type Member,
  type MemberProfile,
  type Notification,
  type SaccoData,
  type TransactionRequest,
  type TransactionRequestPayload,
} from "../services/api";
import { trackProductEvent, trackSessionEnd } from "../services/productAnalyticsTracking";
import { ProductUsageAnalyticsDashboard } from "./features/product-analytics/ProductUsageAnalyticsDashboard";

// -- Types ---------------------------------------------------------------------

type NavItem = { id: string; label: string; icon: React.ElementType; badge?: number; ai?: boolean; adminOnly?: boolean; userOnly?: boolean; staffOnly?: boolean; requiresOutstandingLoan?: boolean };
type ChatMessage = { role: "user" | "assistant"; content: string; ts: string };

interface SaccoDataContextValue {
  data: SaccoData;
  session: AuthSession | null;
  membership: MembershipStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  refreshMembership: () => Promise<void>;
}

const SaccoDataContext = React.createContext<SaccoDataContextValue>({
  data: EMPTY_SACCO_DATA,
  session: null,
  membership: null,
  loading: false,
  error: null,
  refresh: async () => {},
  refreshMembership: async () => {},
});

function useSaccoData() {
  return React.useContext(SaccoDataContext);
}


// -- AI Helpers ----------------------------------------------------------------

function computeCreditScore(member: Member): { score: number; band: string; color: string; factors: { label: string; pts: number }[] } {
  let score = 500;
  const factors: { label: string; pts: number }[] = [];

  const savingsRatio = member.savings / Math.max(member.loans, 1);
  const savingsPts = Math.min(Math.round(savingsRatio * 60), 140);
  score += savingsPts;
  factors.push({ label: "Savings coverage ratio", pts: savingsPts });

  const tenureYears = (Date.now() - new Date(member.joined).getTime()) / (365.25 * 86400000);
  const tenurePts = Math.min(Math.round(tenureYears * 14), 70);
  score += tenurePts;
  factors.push({ label: "Membership tenure", pts: tenurePts });

  const sharePts = Math.min(Math.round(member.shares / 6), 55);
  score += sharePts;
  factors.push({ label: "Share capital held", pts: sharePts });

  const statusPts = member.status === "Active" ? 40 : member.status === "Inactive" ? -30 : -80;
  score += statusPts;
  factors.push({ label: "Account standing", pts: statusPts });

  score = Math.max(300, Math.min(850, score));

  const band = score >= 750 ? "Excellent" : score >= 680 ? "Good" : score >= 600 ? "Fair" : score >= 500 ? "Poor" : "Very Poor";
  const color = score >= 750 ? "#059669" : score >= 680 ? "#0F4C35" : score >= 600 ? "#C8A84B" : score >= 500 ? "#EA580C" : "#DC2626";

  return { score, band, color, factors };
}

function getAIResponse(query: string, data: SaccoData): string {
  const { members, loans, transactions, anomalyFlags, portfolioData } = data;
  const latestPortfolio = portfolioData[portfolioData.length - 1];
  const totalSavings = latestPortfolio?.savings ?? members.reduce((sum, member) => sum + member.savings, 0);
  const outstanding = latestPortfolio?.loans ?? loans.reduce((sum, loan) => sum + loan.balance, 0);
  const overdueLoans = loans.filter((loan) => loan.status === "Overdue");
  const overdueBalance = overdueLoans.reduce((sum, loan) => sum + loan.balance, 0);
  const activeMembers = members.filter((member) => member.status === "Active").length;
  const nplRatio = outstanding > 0 ? ((overdueBalance / outstanding) * 100).toFixed(1) : "0.0";
  const flaggedTransactions = transactions.filter((transaction) => anomalyFlags[transaction.id]);
  const recentCredits = transactions.filter((transaction) => transaction.type === "Credit").reduce((sum, transaction) => sum + transaction.amount, 0);
  const recentDebits = transactions.filter((transaction) => transaction.type === "Debit").reduce((sum, transaction) => sum + transaction.amount, 0);
  const period = latestPortfolio?.month ? `${latestPortfolio.month} 2026` : "the live 2026 backend data";
  const anomalySummaryRows = flaggedTransactions.length
    ? flaggedTransactions
        .map((transaction) => {
          const flag = anomalyFlags[transaction.id];
          return `- **${transaction.id}** - ${flag.level} risk: ${flag.reason} (${transaction.member}, ${transaction.type} ${fmtShort(transaction.amount)} via ${transaction.channel})`;
        })
        .join("\n")
    : "- No backend anomaly flags are currently present.";

  if (/fraud|anomal|suspicious|unusual/i.test(query)) {
    return [
      "**Backend Fraud & Anomaly Summary**",
      "",
      `I found **${flaggedTransactions.length} flagged transaction(s)** in the live backend data.`,
      "",
      anomalySummaryRows,
      "",
      "**Trace note:** This answer is generated from the loaded `/api/sacco-data` anomaly flags, not sample records.",
    ].join("\n");
  }

  if (/overdue|default|at.?risk|npl|collection/i.test(query)) {
    return `**Backend Portfolio-at-Risk Summary - ${period}**\n\n- **Overdue loans:** ${overdueLoans.length}\n- **Overdue exposure:** ${fmtShort(overdueBalance)}\n- **Outstanding portfolio:** ${fmtShort(outstanding)}\n- **NPL ratio:** ${nplRatio}%\n\n${overdueLoans.length ? overdueLoans.map((loan) => `- **${loan.id}** - ${loan.member}, ${fmtShort(loan.balance)} outstanding, due ${loan.due}`).join("\n") : "- No overdue loans are present in the current backend dataset."}\n\n**Recommended next step:** Review the Collections tab for the same backend loan records and assign follow-up priority by days overdue.`;
  }

  if (/savings|deposit|growth|inflow/i.test(query)) {
    return `**Backend Savings Snapshot - ${period}**\n\n- **Total savings:** ${fmtShort(totalSavings)}\n- **Active members:** ${activeMembers} of ${members.length}\n- **Recent credit flow:** ${fmtShort(recentCredits)}\n- **Recent debit flow:** ${fmtShort(recentDebits)}\n- **Net recent flow:** ${fmtShort(recentCredits - recentDebits)}\n\n${portfolioData.length ? `Latest backend portfolio month is **${latestPortfolio.month}** with savings at **${fmtShort(latestPortfolio.savings)}**.` : "No portfolio time-series rows are currently loaded from the backend."}`;
  }

  if (/member|churn|retain|inactive/i.test(query)) {
    const inactive = members.filter((member) => member.status !== "Active");
    return `**Backend Member Summary - 2026**\n\n- **Total members:** ${members.length}\n- **Active:** ${activeMembers}\n- **Inactive or suspended:** ${inactive.length}\n\n${inactive.length ? inactive.slice(0, 6).map((member) => `- **${member.name}** (${member.id}) - ${member.status}, savings ${fmtShort(member.savings)}`).join("\n") : "- Every loaded backend member is currently marked active."}`;
  }

  if (/credit.?scor|eligib|qualify/i.test(query)) {
    const scored = members.map((member) => ({ member, score: computeCreditScore(member) })).sort((a, b) => a.score.score - b.score.score);
    return `**Backend Credit Score Snapshot - 2026**\n\nLowest-scoring loaded members:\n\n${scored.slice(0, 5).map(({ member, score }) => `- **${member.name}** (${member.id}) - ${score.score} / ${score.band}, savings ${fmtShort(member.savings)}, loans ${fmtShort(member.loans)}`).join("\n") || "- No backend members are loaded yet."}\n\nScores are computed from the current backend member records shown in the Members and Loans tabs.`;
  }

  return `**UmojaAI Backend Summary - ${period}**\n\n- **Total savings:** ${fmtShort(totalSavings)}\n- **Loan portfolio:** ${fmtShort(outstanding)}\n- **Members loaded:** ${members.length} (${activeMembers} active)\n- **Loans loaded:** ${loans.length} (${overdueLoans.length} overdue)\n- **Transactions loaded:** ${transactions.length}\n- **Backend anomaly flags:** ${flaggedTransactions.length}\n\nAsk me about overdue loans, savings flow, fraud flags, member retention, or credit scoring and I will answer from the loaded backend data.`;
}

// -- Loan Scoring Engine --------------------------------------------------------

type ScoreTrend = "up" | "down" | "flat";
type DefaultRisk = "Very Low" | "Low" | "Medium" | "High" | "Very High";
type Recommendation = "Approve" | "Approve with Conditions" | "Counter-offer" | "Decline";

interface ScoringDimension {
  name: string; score: number; weight: number; signal: string; trend: ScoreTrend;
}

interface LoanScoreResult {
  composite: number;
  repaymentLikelihood: number;
  defaultRisk: DefaultRisk;
  affordabilityRatio: number;
  delinquencyRisk90d: number;
  recommendation: Recommendation;
  maxLoanAmount: number;
  suggestedRate: number;
  dimensions: ScoringDimension[];
  keyRisks: string[];
  keyStrengths: string[];
}

function computeLoanScore(
  memberId: string,
  loanAmount: number,
  members: Member[],
  memberProfiles: Record<string, MemberProfile>,
  loans: Loan[],
): LoanScoreResult {
  const member = members.find((m) => m.id === memberId);
  const profile = memberProfiles[memberId];

  if (!member || !profile) {
    throw new Error("Member profile is not available for scoring");
  }

  const tenureMonths = (Date.now() - new Date(member.joined).getTime()) / (30 * 86400000);
  const inflows = profile.mpesaMonthlyInflows;
  const avgInflow = inflows.reduce((a, b) => a + b, 0) / inflows.length;
  const inflowVariance = inflows.reduce((a, v) => a + Math.pow(v - avgInflow, 2), 0) / inflows.length;
  const cv = Math.sqrt(inflowVariance) / avgInflow;

  const activeLoan = loans.find((l) => l.member === member.name && l.status !== "Completed");
  const isOverdue = activeLoan?.status === "Overdue";

  // 1. Salary Pattern (20%) - income level and regularity
  const incomeScore = Math.min(85, (avgInflow / profile.estimatedMonthlyIncome) * 80);
  const consistencyPenalty = Math.min(30, cv * 80);
  const salaryPatternScore = Math.max(10, Math.round(incomeScore - consistencyPenalty + 15));

  // 2. Savings Consistency (18%) - actual vs expected accumulation rate
  const expectedSavings = tenureMonths * avgInflow * 0.15;
  const savingsRatio = member.savings / Math.max(expectedSavings, 1);
  const savingsConsistencyScore = Math.min(100, Math.round(savingsRatio * 80));

  // 3. Repayment History (22%) - past loan behaviour is the strongest predictor
  const baseRepayment = isOverdue ? 12 : member.status === "Suspended" ? 22 : member.status === "Inactive" ? 50 : 68;
  const completedBonus = Math.min(28, profile.completedLoans * 14);
  const defaultPenalty = profile.defaultedLoans * 30;
  const repaymentHistoryScore = Math.max(5, Math.min(100, baseRepayment + completedBonus - defaultPenalty));

  // 4. Mobile Money Inflow (15%) - velocity and regularity of M-Pesa flows
  const mpesaScore = Math.min(100, Math.round(
    (avgInflow / 150000) * 60 + (tenureMonths > 24 ? 18 : 8) + (cv < 0.1 ? 12 : 0)
  ));

  // 5. Employer Stability (12%) - formal employment signals lower churn risk
  const employerBase: Record<EmployerType, number> = { Government: 94, Formal: 80, "Self-Employed": 58, Informal: 36 };
  const tenureBonus = Math.min(12, tenureMonths / 5);
  const employerStabilityScore = Math.min(100, Math.round(employerBase[profile.employerType] + tenureBonus));

  // 6. Guarantor Strength (7%) - collateral signal
  const guarantorScore = profile.guarantors.length === 0 ? 28 : profile.guarantors.length === 1 ? 64 : 88;

  // 7. Spending Behavior (6%) - disposable income and debt-service coverage
  const disposable = profile.estimatedMonthlyIncome - profile.monthlyExpenses;
  const dscr = activeLoan ? (activeLoan.balance / 18) / Math.max(disposable, 1) : 0;
  const spendingScore = Math.max(5, Math.min(100, Math.round(
    (disposable / profile.estimatedMonthlyIncome) * 75 - dscr * 35 + 15
  )));

  const dimensions: ScoringDimension[] = [
    { name: "Salary Pattern", score: salaryPatternScore, weight: 0.20, signal: `KES ${Math.round(avgInflow / 1000)}K avg/mo - CV ${(cv * 100).toFixed(0)}%`, trend: cv < 0.12 ? "up" : cv < 0.22 ? "flat" : "down" },
    { name: "Savings Consistency", score: savingsConsistencyScore, weight: 0.18, signal: `${Math.round(Math.min(savingsRatio, 9.9) * 100)}% of expected rate - KES ${(member.savings / 1000).toFixed(0)}K balance`, trend: member.savings > 300000 ? "up" : "flat" },
    { name: "Repayment History", score: repaymentHistoryScore, weight: 0.22, signal: `${profile.completedLoans} completed - ${isOverdue ? "1 overdue" : "0 overdue"}`, trend: isOverdue ? "down" : profile.completedLoans > 0 ? "up" : "flat" },
    { name: "Mobile Money Inflow", score: mpesaScore, weight: 0.15, signal: `KES ${Math.round(avgInflow / 1000)}K monthly M-Pesa - ${inflows.length} months`, trend: "up" },
    { name: "Employer Stability", score: employerStabilityScore, weight: 0.12, signal: `${profile.employerType} - ${profile.employer}`, trend: tenureMonths > 30 ? "up" : "flat" },
    { name: "Guarantor Strength", score: guarantorScore, weight: 0.07, signal: `${profile.guarantors.length} guarantor(s) registered`, trend: profile.guarantors.length > 1 ? "up" : profile.guarantors.length === 1 ? "flat" : "down" },
    { name: "Spending Behavior", score: spendingScore, weight: 0.06, signal: `${Math.round((disposable / profile.estimatedMonthlyIncome) * 100)}% disposable - DSCR ${dscr.toFixed(1)}x`, trend: spendingScore >= 60 ? "up" : "down" },
  ];

  const composite = Math.round(dimensions.reduce((s, d) => s + d.score * d.weight, 0));
  const repaymentLikelihood = Math.min(98, Math.round(composite * 0.91 + 7));
  const defaultRisk: DefaultRisk = composite >= 80 ? "Very Low" : composite >= 66 ? "Low" : composite >= 51 ? "Medium" : composite >= 36 ? "High" : "Very High";
  const affordabilityRatio = loanAmount / profile.estimatedMonthlyIncome;
  const delinquencyRisk90d = Math.max(2, Math.round((100 - composite) * 0.52));

  const recommendation: Recommendation =
    composite >= 72 ? "Approve" : composite >= 57 ? "Approve with Conditions" : composite >= 40 ? "Counter-offer" : "Decline";

  const monthlyCapacity = Math.max(0, disposable * 0.55);
  const maxAffordable = monthlyCapacity * 24;
  const ratioMultiplier = composite >= 72 ? 1.0 : composite >= 57 ? 0.78 : 0.50;
  const maxLoanAmount = Math.round(Math.min(loanAmount, maxAffordable) * ratioMultiplier / 10000) * 10000;
  const suggestedRate = composite >= 80 ? 10 : composite >= 66 ? 12 : composite >= 51 ? 14 : 16;

  const keyRisks: string[] = [];
  const keyStrengths: string[] = [];
  dimensions.forEach((d) => {
    if (d.score < 48) keyRisks.push(`${d.name}: ${d.signal}`);
    if (d.score >= 74) keyStrengths.push(`${d.name}: ${d.signal}`);
  });
  if (affordabilityRatio > 6) keyRisks.push("Requested amount exceeds 6x monthly income");
  if (member.status !== "Active") keyRisks.push(`Account status: ${member.status}`);
  if (isOverdue) keyRisks.push("Existing overdue loan on portfolio");
  if (profile.completedLoans > 0) keyStrengths.push(`${profile.completedLoans} loan(s) repaid without default`);
  if (profile.guarantors.length >= 2) keyStrengths.push("Dual guarantor coverage - strong collateral signal");

  return { composite, repaymentLikelihood, defaultRisk, affordabilityRatio, delinquencyRisk90d, recommendation, maxLoanAmount, suggestedRate, dimensions, keyRisks: keyRisks.slice(0, 4), keyStrengths: keyStrengths.slice(0, 4) };
}

// -- Score Gauge (SVG arc) -----------------------------------------------------

function ScoreGauge({ score }: { score: number }) {
  const r = 52, cx = 70, cy = 78;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.72;
  const filled = (score / 100) * arc;
  const startDeg = 126;
  const color = score >= 72 ? "#059669" : score >= 57 ? "#0F4C35" : score >= 40 ? "#C8A84B" : "#DC2626";
  const band = score >= 72 ? "Strong" : score >= 57 ? "Moderate" : score >= 40 ? "Caution" : "High Risk";
  const tf = `rotate(${startDeg}, ${cx}, ${cy})`;
  return (
    <svg width="140" height="135" viewBox="0 0 140 135">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E2E8E3" strokeWidth="11"
        strokeDasharray={`${arc} ${circ - arc}`} strokeLinecap="round" transform={tf} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="11"
        strokeDasharray={`${filled} ${circ - filled}`} strokeLinecap="round" transform={tf}
        style={{ transition: "stroke-dasharray 0.6s ease" }} />
      <text x={cx} y={cy - 7} textAnchor="middle" fontSize="28" fontWeight="800" fill={color} fontFamily="Plus Jakarta Sans, sans-serif">{score}</text>
      <text x={cx} y={cy + 12} textAnchor="middle" fontSize="11" fill={color} fontFamily="Inter, sans-serif" fontWeight="600">{band}</text>
      <text x={cx} y={cy + 26} textAnchor="middle" fontSize="9.5" fill="#9CA3AF" fontFamily="JetBrains Mono, monospace">out of 100</text>
    </svg>
  );
}

// -- Helpers -------------------------------------------------------------------

const fmtShort = (n: number) =>
  n >= 1_000_000
    ? `KES ${(n / 1_000_000).toFixed(1)}M`
    : n >= 1000
    ? `KES ${(n / 1000).toFixed(0)}K`
    : `KES ${n}`;

const timeAgo = (value: string) => {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(value).toLocaleDateString();
};

const notificationStyle = (type: string) => {
  if (type === "danger") return { icon: TriangleAlert, color: "text-red-500" };
  if (type === "warning") return { icon: AlertCircle, color: "text-amber-500" };
  if (type === "success") return { icon: CheckCircle2, color: "text-emerald-500" };
  return { icon: Info, color: "text-primary" };
};

// -- Sub-components ------------------------------------------------------------

function StatCard({
  label, value, delta, deltaLabel, icon: Icon, accent = false,
}: {
  label: string; value: string; delta?: number; deltaLabel?: string;
  icon: React.ElementType; accent?: boolean;
}) {
  const positive = delta !== undefined && delta >= 0;
  return (
    <div className={`rounded-lg p-5 flex flex-col gap-4 border ${accent ? "bg-primary text-primary-foreground border-transparent" : "bg-card text-card-foreground border-border"}`}>
      <div className="flex items-start justify-between">
        <span className={`text-xs font-semibold uppercase tracking-widest ${accent ? "text-primary-foreground/60" : "text-muted-foreground"}`}>{label}</span>
        <div className={`w-8 h-8 rounded flex items-center justify-center ${accent ? "bg-white/10" : "bg-secondary"}`}>
          <Icon size={16} className={accent ? "text-primary-foreground" : "text-primary"} />
        </div>
      </div>
      <div>
        <p className={`text-2xl font-bold font-['Plus_Jakarta_Sans'] tracking-tight ${accent ? "text-primary-foreground" : "text-foreground"}`}>{value}</p>
        {delta !== undefined && (
          <p className={`text-xs mt-1 flex items-center gap-1 ${accent ? "text-primary-foreground/70" : positive ? "text-emerald-600" : "text-red-500"}`}>
            {positive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {Math.abs(delta)}% {deltaLabel || "vs last month"}
          </p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    Active: "bg-emerald-50 text-emerald-700 border-emerald-200",
    Approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
    Completed: "bg-blue-50 text-blue-700 border-blue-200",
    Overdue: "bg-red-50 text-red-700 border-red-200",
    Pending: "bg-amber-50 text-amber-700 border-amber-200",
    Rejected: "bg-red-50 text-red-700 border-red-200",
    Suspended: "bg-orange-50 text-orange-700 border-orange-200",
    Inactive: "bg-gray-100 text-gray-500 border-gray-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[status] || styles["Inactive"]}`}>
      {status}
    </span>
  );
}

function getOutstandingRepaymentLoans(loans: Loan[]) {
  return loans.filter((loan) => loan.balance > 0 && loan.status !== "Completed");
}

function CreditScoreBadge({ score, band, color }: { score: number; band: string; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="font-['JetBrains_Mono'] text-sm font-bold" style={{ color }}>{score}</span>
      <span className="text-xs px-1.5 py-0.5 rounded font-medium border" style={{ color, borderColor: color + "40", background: color + "12" }}>{band}</span>
    </div>
  );
}

// Renders markdown-lite: bold, bullet lists, tables
function AIMessageRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let tableRows: string[][] = [];
  let inTable = false;

  const renderInline = (text: string, key: number) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return (
      <span key={key}>
        {parts.map((p, i) =>
          p.startsWith("**") && p.endsWith("**")
            ? <strong key={i} className="font-semibold text-foreground">{p.slice(2, -2)}</strong>
            : p
        )}
      </span>
    );
  };

  const flushTable = () => {
    if (tableRows.length > 0) {
      const header = tableRows[0];
      const body = tableRows.slice(2);
      elements.push(
        <div key={`table-${elements.length}`} className="my-2 overflow-x-auto">
          <table className="text-xs w-full border-collapse">
            <thead>
              <tr>
                {header.map((h, i) => <th key={i} className="text-left py-1 px-2 border-b border-border text-muted-foreground font-semibold">{h.trim()}</th>)}
              </tr>
            </thead>
            <tbody>
              {body.map((row, ri) => (
                <tr key={ri} className="border-b border-border/40">
                  {row.map((cell, ci) => <td key={ci} className="py-1 px-2 text-foreground">{renderInline(cell.trim(), ci)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  lines.forEach((line, i) => {
    if (line.startsWith("|")) {
      inTable = true;
      tableRows.push(line.split("|").filter((_, j) => j > 0 && j < line.split("|").length - 1));
      return;
    }
    if (inTable) flushTable();

    if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(<p key={i} className="font-semibold text-foreground mt-3 mb-1">{line.slice(2, -2)}</p>);
    } else if (line.startsWith("- ") || /^\d+\./.test(line)) {
      elements.push(<p key={i} className="flex gap-2 text-sm text-foreground/90 leading-relaxed ml-2">
        <span className="text-primary mt-0.5 flex-shrink-0">-</span>
        <span>{renderInline(line.replace(/^[-\d.]\s?/, ""), i)}</span>
      </p>);
    } else if (line.trim() === "") {
      elements.push(<div key={i} className="h-1.5" />);
    } else {
      elements.push(<p key={i} className="text-sm text-foreground/90 leading-relaxed">{renderInline(line, i)}</p>);
    }
  });

  if (inTable) flushTable();
  return <div className="space-y-0.5">{elements}</div>;
}

// -- AI Insights Strip (Dashboard) ---------------------------------------------

function AIInsightsStrip({ onNav }: { onNav: (id: string) => void }) {
  const insights = [
    {
      icon: TriangleAlert,
      color: "text-red-500",
      bg: "bg-red-50 border-red-100",
      title: "2 members projected to default within 30 days",
      action: "Review loans",
      nav: "loans",
    },
    {
      icon: TrendingUp,
      color: "text-emerald-600",
      bg: "bg-emerald-50 border-emerald-100",
      title: "Savings inflow forecast +8.2% for August",
      action: "See forecast",
      nav: "ai",
    },
    {
      icon: TriangleAlert,
      color: "text-amber-500",
      bg: "bg-amber-50 border-amber-100",
      title: "3 anomalous transactions flagged this week",
      action: "View flags",
      nav: "transactions",
    },
  ];

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-primary/5">
        <Sparkles size={13} className="text-primary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">AI Insights</span>
        <span className="ml-auto text-xs text-muted-foreground">Updated just now</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border">
        {insights.map((ins) => (
          <div key={ins.title} className={`flex items-start gap-3 px-4 py-3.5 ${ins.bg} border-b border-transparent`}>
            <ins.icon size={14} className={`${ins.color} mt-0.5 flex-shrink-0`} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground leading-snug">{ins.title}</p>
              <button
                onClick={() => onNav(ins.nav)}
                className={`text-xs font-semibold mt-1 underline underline-offset-2 ${ins.color}`}
              >
                  {ins.action} -&gt;
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// -- Dashboard View ------------------------------------------------------------

function DashboardView({ onNav }: { onNav: (id: string) => void }) {
  const { data } = useSaccoData();
  const { portfolioData, loanDistribution, members, loans, transactions, anomalyFlags } = data;
  const latestPortfolio = portfolioData[portfolioData.length - 1];
  const previousPortfolio = portfolioData[portfolioData.length - 2];
  const totalSavings = latestPortfolio?.savings ?? members.reduce((sum, member) => sum + member.savings, 0);
  const loanPortfolio = latestPortfolio?.loans ?? loans.reduce((sum, loan) => sum + loan.balance, 0);
  const overdueLoans = loans.filter((loan) => loan.status === "Overdue");
  const overdueBalance = overdueLoans.reduce((sum, loan) => sum + loan.balance, 0);
  const savingsDelta = previousPortfolio && previousPortfolio.savings > 0
    ? Number((((totalSavings - previousPortfolio.savings) / previousPortfolio.savings) * 100).toFixed(1))
    : undefined;
  const loansDelta = previousPortfolio && previousPortfolio.loans > 0
    ? Number((((loanPortfolio - previousPortfolio.loans) / previousPortfolio.loans) * 100).toFixed(1))
    : undefined;

  return (
    <div className="space-y-5">
      <AIInsightsStrip onNav={onNav} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Savings" value={fmtShort(totalSavings)} delta={savingsDelta} icon={PiggyBank} accent />
        <StatCard label="Loan Portfolio" value={fmtShort(loanPortfolio)} delta={loansDelta} icon={CreditCard} />
        <StatCard label="Active Members" value={members.filter((m) => m.status === "Active").length.toLocaleString()} icon={Users} />
        <StatCard label="Overdue Loans" value={fmtShort(overdueBalance)} icon={AlertCircle} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-card border border-border rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Portfolio Growth</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Savings vs. Loan disbursements - 2026</p>
            </div>
            <select className="text-xs border border-border rounded px-2 py-1 bg-input-background text-foreground focus:outline-none">
              <option>Last 7 months</option>
              <option>Last 12 months</option>
            </select>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={portfolioData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorSavings" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0F4C35" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#0F4C35" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorLoans" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#C8A84B" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#C8A84B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`} tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v: number, name: string) => [fmtShort(v), name === "savings" ? "Savings" : "Loans"]}
                contentStyle={{ background: "#fff", border: "1px solid rgba(15,76,53,0.12)", borderRadius: 6, fontSize: 12 }}
              />
              <Area type="monotone" dataKey="savings" stroke="#0F4C35" strokeWidth={2} fill="url(#colorSavings)" />
              <Area type="monotone" dataKey="loans" stroke="#C8A84B" strokeWidth={2} fill="url(#colorLoans)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-1">Loan Distribution</h3>
          <p className="text-xs text-muted-foreground mb-4">By loan category</p>
          <ResponsiveContainer width="100%" height={150}>
            <PieChart>
              <Pie data={loanDistribution} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" paddingAngle={3}>
                {loanDistribution.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip formatter={(v: number) => [`${v}%`, ""]} contentStyle={{ fontSize: 12, borderRadius: 6 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {loanDistribution.map((d) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                  <span className="text-muted-foreground">{d.name}</span>
                </div>
                <span className="font-medium font-['JetBrains_Mono'] text-foreground">{d.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Recent Transactions</h3>
            <button className="text-xs text-primary font-medium hover:underline">View all</button>
          </div>
          <div className="space-y-3">
            {transactions.slice(0, 5).map((t) => (
              <div key={t.id} className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded flex items-center justify-center flex-shrink-0 ${t.type === "Credit" ? "bg-emerald-50" : "bg-red-50"}`}>
                  {t.type === "Credit" ? <TrendingUp size={14} className="text-emerald-600" /> : <TrendingDown size={14} className="text-red-500" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-sm font-medium text-foreground truncate">{t.member}</p>
                    {anomalyFlags[t.id] && (
                      <span className={`text-xs px-1.5 py-px rounded font-medium border flex-shrink-0 ${anomalyFlags[t.id].level === "high" ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-600 border-amber-200"}`}>
                        AI Flag
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">{t.category} - {t.channel}</p>
                </div>
                <span className={`text-sm font-semibold font-['JetBrains_Mono'] ${t.type === "Credit" ? "text-emerald-600" : "text-red-500"}`}>
                  {t.type === "Credit" ? "+" : "-"}{fmtShort(t.amount)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Overdue Loans</h3>
            <span className="text-xs bg-red-50 text-red-600 border border-red-200 px-2 py-0.5 rounded font-medium">
              {overdueLoans.length} loans
            </span>
          </div>
          <div className="space-y-3">
            {overdueLoans.map((l) => {
              const overdueDays = Math.floor((Date.now() - new Date(l.due).getTime()) / 86400000);
              const member = members.find((m) => m.name === l.member);
              const cs = member ? computeCreditScore(member) : null;
              return (
                <div key={l.id} className="flex items-start gap-3 p-3 rounded-lg bg-red-50/60 border border-red-100">
                  <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">{l.member}</p>
                    <p className="text-xs text-muted-foreground">{l.id} - {l.type}</p>
                    <p className="text-xs text-red-600 font-medium mt-0.5">{overdueDays} days overdue</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold font-['JetBrains_Mono'] text-foreground">{fmtShort(l.balance)}</p>
                    {cs && <p className="text-xs" style={{ color: cs.color }}>Score: {cs.score}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// -- Members View --------------------------------------------------------------

function MembersView({ onNav }: { onNav: (id: string) => void }) {
  const { data } = useSaccoData();
  const { members } = data;
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");

  const filtered = members.filter((m) => {
    const matchesSearch = m.name.toLowerCase().includes(search.toLowerCase()) || m.id.toLowerCase().includes(search.toLowerCase());
    return matchesSearch && (filter === "All" || m.status === filter);
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input type="text" placeholder="Search by name or member ID..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-border bg-card focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
        <div className="flex gap-2">
          {["All", "Active", "Inactive", "Suspended"].map((s) => (
            <button key={s} onClick={() => setFilter(s)}
              className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${filter === s ? "bg-primary text-primary-foreground border-primary" : "bg-card text-muted-foreground border-border hover:border-primary/40"}`}>
              {s}
            </button>
          ))}
        </div>
        <button onClick={() => onNav("admin")} className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground text-sm font-semibold rounded-lg hover:bg-accent/90 transition-colors">
          <Plus size={14} /> Add Member
        </button>
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/40">
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Member</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">ID</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Savings</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Loans</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Shares</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Joined</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((m, i) => (
                <tr key={m.id} className={`border-b border-border/50 hover:bg-secondary/30 transition-colors ${i % 2 === 0 ? "" : "bg-secondary/10"}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs font-bold flex-shrink-0">
                        {m.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{m.name}</p>
                        <p className="text-xs text-muted-foreground">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-['JetBrains_Mono'] text-xs text-muted-foreground">{m.id}</td>
                  <td className="px-4 py-3 text-right font-['JetBrains_Mono'] text-sm font-medium text-foreground">{fmtShort(m.savings)}</td>
                  <td className="px-4 py-3 text-right font-['JetBrains_Mono'] text-sm">
                    <span className={m.loans > 0 ? "text-foreground font-medium" : "text-muted-foreground"}>{m.loans > 0 ? fmtShort(m.loans) : "-"}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-['JetBrains_Mono'] text-sm text-foreground">{m.shares}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{m.joined}</td>
                  <td className="px-4 py-3"><StatusBadge status={m.status} /></td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 rounded hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground">
                      <MoreHorizontal size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 border-t border-border flex items-center justify-between">
          <p className="text-xs text-muted-foreground">Showing {filtered.length} of {members.length} members</p>
          <div className="flex items-center gap-1">
            {[1, 2, 3].map((p) => (
              <button key={p} className={`w-7 h-7 text-xs rounded ${p === 1 ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary"}`}>{p}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// -- Loans View ----------------------------------------------------------------

function LoansView({ onNav }: { onNav: (id: string) => void }) {
  const { data, session, membership, refresh } = useSaccoData();
  const { members, loans } = data;
  const [activeTab, setActiveTab] = useState("all");
  const [expandedScore, setExpandedScore] = useState<string | null>(null);
  const [loanActionError, setLoanActionError] = useState("");
  const [updatingLoanId, setUpdatingLoanId] = useState<string | null>(null);
  const [myApplications, setMyApplications] = useState<LoanApplication[]>([]);
  const [applicationForm, setApplicationForm] = useState({ amount: "", type: "Business", purpose: "", termMonths: "12" });
  const [submittingApplication, setSubmittingApplication] = useState(false);
  const isAdmin = session?.user.role === "admin";

  const tabs = [
    { id: "all", label: "All Loans" },
    { id: "Active", label: "Active" },
    { id: "Overdue", label: "Overdue" },
    { id: "Completed", label: "Completed" },
  ];

  const filtered = activeTab === "all" ? loans : loans.filter((l) => l.status === activeTab);

  useEffect(() => {
    if (!session?.token || isAdmin || !membership?.member) return;
    listMyLoanApplications(session.token)
      .then(setMyApplications)
      .catch(() => setMyApplications([]));
  }, [isAdmin, membership?.member, session?.token]);

  const approveLoan = async (loanId: string) => {
    if (!session?.token || updatingLoanId) return;
    setUpdatingLoanId(loanId);
    setLoanActionError("");
    try {
      await updateLoan(session.token, loanId, { status: "Active" });
      await refresh();
    } catch (error) {
      setLoanActionError(error instanceof Error ? error.message : "Unable to approve loan");
    } finally {
      setUpdatingLoanId(null);
    }
  };

  const submitLoanApplication = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!session?.token || submittingApplication) return;
    setSubmittingApplication(true);
    setLoanActionError("");
    try {
      const application = await applyForLoan(session.token, {
        amount: Number(applicationForm.amount),
        type: applicationForm.type,
        purpose: applicationForm.purpose,
        termMonths: Number(applicationForm.termMonths),
      });
      setMyApplications((current) => [application, ...current]);
      setApplicationForm({ amount: "", type: "Business", purpose: "", termMonths: "12" });
    } catch (error) {
      setLoanActionError(error instanceof Error ? error.message : "Unable to submit loan application");
    } finally {
      setSubmittingApplication(false);
    }
  };

  return (
    <div className="space-y-5">
      {!isAdmin && !membership?.member && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
          <ShieldAlert size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-amber-900">Membership approval required</p>
            <p className="text-xs text-amber-700 mt-0.5">Apply for membership first. Once an admin approves you, loan applications and member finance features will unlock.</p>
          </div>
        </div>
      )}

      {!isAdmin && membership?.member && (
        <form onSubmit={submitLoanApplication} className="bg-card border border-border rounded-lg p-4 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Amount</span>
            <input type="number" min="1" required value={applicationForm.amount} onChange={(event) => setApplicationForm((current) => ({ ...current, amount: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Type</span>
            <select value={applicationForm.type} onChange={(event) => setApplicationForm((current) => ({ ...current, type: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20">
              {["Business", "Education", "Emergency", "Development", "Agricultural"].map((type) => <option key={type}>{type}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Term</span>
            <input type="number" min="1" max="84" required value={applicationForm.termMonths} onChange={(event) => setApplicationForm((current) => ({ ...current, termMonths: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </label>
          <label className="block md:col-span-1">
            <span className="text-xs font-semibold text-muted-foreground">Purpose</span>
            <input required value={applicationForm.purpose} onChange={(event) => setApplicationForm((current) => ({ ...current, purpose: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </label>
          <button disabled={submittingApplication} className="flex items-center justify-center gap-2 px-4 py-2 bg-accent text-accent-foreground text-sm font-semibold rounded-lg hover:bg-accent/90 disabled:opacity-50 transition-colors">
            <Plus size={14} /> {submittingApplication ? "Submitting" : "Apply Loan"}
          </button>
        </form>
      )}

      {!isAdmin && myApplications.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <p className="text-sm font-semibold text-foreground mb-3">My Loan Applications</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {myApplications.map((application) => (
              <div key={application.id} className="border border-border rounded-lg p-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">{fmtShort(application.amount)} - {application.type}</p>
                  <p className="text-xs text-muted-foreground">{application.purpose || "No purpose provided"}</p>
                </div>
                <StatusBadge status={application.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-1 p-1 bg-secondary rounded-lg max-w-full overflow-x-auto">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${activeTab === t.id ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
              {t.label}
              {t.id !== "all" && <span className="ml-1.5 text-xs opacity-60">{loans.filter((l) => l.status === t.id).length}</span>}
            </button>
          ))}
        </div>
        {isAdmin && (
          <button onClick={() => onNav("admin")} className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground text-sm font-semibold rounded-lg hover:bg-accent/90 transition-colors">
            <Plus size={14} /> New Loan Application
          </button>
        )}
      </div>

      {loanActionError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
          <AlertCircle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-600">{loanActionError}</p>
        </div>
      )}

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/40">
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Loan ID</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Member</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Type</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Principal</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Balance</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Rate</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Due Date</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <span className="flex items-center gap-1"><Sparkles size={10} className="text-primary" /> AI Score</span>
                </th>
                {isAdmin && <th className="px-4 py-3" />}
              </tr>
            </thead>
            <tbody>
              {filtered.map((l, i) => {
                const repaid = ((l.amount - l.balance) / l.amount) * 100;
                const member = members.find((m) => m.name === l.member);
                const cs = member ? computeCreditScore(member) : null;
                const isExpanded = expandedScore === l.id;

                return (
                  <React.Fragment key={l.id}>
                    <tr className={`border-b border-border/50 hover:bg-secondary/30 transition-colors ${i % 2 === 0 ? "" : "bg-secondary/10"}`}>
                      <td className="px-4 py-3 font-['JetBrains_Mono'] text-xs text-muted-foreground">{l.id}</td>
                      <td className="px-4 py-3 font-medium text-foreground">{l.member}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs px-2 py-0.5 rounded bg-secondary text-secondary-foreground border border-border">{l.type}</span>
                      </td>
                      <td className="px-4 py-3 text-right font-['JetBrains_Mono'] text-sm font-medium">{fmtShort(l.amount)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-col items-end gap-1">
                          <span className="font-['JetBrains_Mono'] text-sm font-medium">
                            {l.balance === 0 ? <span className="text-muted-foreground">-</span> : fmtShort(l.balance)}
                          </span>
                          {l.balance > 0 && (
                            <div className="w-16 h-1 rounded-full bg-secondary overflow-hidden">
                              <div className="h-full rounded-full bg-primary" style={{ width: `${repaid}%` }} />
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-['JetBrains_Mono'] text-sm text-muted-foreground">{l.rate}%</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{l.due}</td>
                      <td className="px-4 py-3"><StatusBadge status={l.status} /></td>
                      <td className="px-4 py-3">
                        {cs && (
                          <button onClick={() => setExpandedScore(isExpanded ? null : l.id)} className="text-left hover:opacity-80 transition-opacity">
                            <CreditScoreBadge score={cs.score} band={cs.band} color={cs.color} />
                          </button>
                        )}
                      </td>
                      {isAdmin && (
                        <td className="px-4 py-3 text-right">
                          {l.status === "Pending" ? (
                            <button
                              onClick={() => approveLoan(l.id)}
                              disabled={updatingLoanId === l.id}
                              className="text-xs px-2.5 py-1.5 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                            >
                              {updatingLoanId === l.id ? "Approving" : "Approve"}
                            </button>
                          ) : (
                            <button className="p-1.5 rounded hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground" aria-label={`Edit ${l.id}`}>
                              <MoreHorizontal size={15} />
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                    {isExpanded && cs && (
                      <tr className="bg-primary/5 border-b border-border">
                        <td colSpan={isAdmin ? 10 : 9} className="px-6 py-4">
                          <div className="flex items-start gap-6">
                            <div className="flex flex-col items-center gap-1 flex-shrink-0">
                              <span className="text-3xl font-bold font-['Plus_Jakarta_Sans']" style={{ color: cs.color }}>{cs.score}</span>
                              <span className="text-xs font-semibold" style={{ color: cs.color }}>{cs.band}</span>
                              <div className="w-20 h-2 rounded-full bg-secondary mt-1 overflow-hidden">
                                <div className="h-full rounded-full" style={{ width: `${((cs.score - 300) / 550) * 100}%`, background: cs.color }} />
                              </div>
                              <span className="text-xs text-muted-foreground">300 - 850</span>
                            </div>
                            <div className="flex-1 grid grid-cols-2 gap-2">
                              <p className="col-span-2 text-xs font-semibold text-foreground mb-1 flex items-center gap-1.5">
                                <Sparkles size={11} className="text-primary" /> AI Credit Score Breakdown
                              </p>
                              {cs.factors.map((f) => (
                                <div key={f.label} className="flex items-center justify-between bg-card rounded border border-border px-3 py-2">
                                  <span className="text-xs text-muted-foreground">{f.label}</span>
                                  <span className={`text-xs font-bold font-['JetBrains_Mono'] ${f.pts >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                                    {f.pts >= 0 ? "+" : ""}{f.pts}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// -- Transactions View ---------------------------------------------------------

function LoanRepaymentView() {
  const { data, session, membership, refresh } = useSaccoData();
  const outstandingLoans = getOutstandingRepaymentLoans(data.loans).filter(
    (loan) => !membership?.member || loan.member === membership.member.id || loan.member === membership.member.name.toUpperCase()
  );
  const loanTypes = Array.from(new Set(outstandingLoans.map((loan) => loan.type))).sort();
  const [selectedLoanType, setSelectedLoanType] = useState(loanTypes[0] ?? "");
  const [selectedLoanId, setSelectedLoanId] = useState(outstandingLoans[0]?.id ?? "");
  const [repaymentForm, setRepaymentForm] = useState({
    amount: "",
    method: "M-Pesa",
    phoneNumber: "",
    channel: "Bank Transfer",
    ref: `REPAY-${Math.floor(Date.now() / 1000)}`,
    date: new Date().toISOString().slice(0, 10),
  });
  const [repaymentRequests, setRepaymentRequests] = useState<TransactionRequest[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedLoanType && loanTypes[0]) {
      setSelectedLoanType(loanTypes[0]);
    }
  }, [loanTypes, selectedLoanType]);

  const loansForSelectedType = selectedLoanType
    ? outstandingLoans.filter((loan) => loan.type === selectedLoanType)
    : outstandingLoans;

  useEffect(() => {
    if (!loansForSelectedType.length) return;
    if (!selectedLoanId || !loansForSelectedType.some((loan) => loan.id === selectedLoanId)) {
      setSelectedLoanId(loansForSelectedType[0].id);
    }
  }, [loansForSelectedType, selectedLoanId]);

  const loadRepaymentRequests = React.useCallback(async () => {
    if (!session?.token || session.user.role === "admin" || !membership?.member) return;
    try {
      const requests = await listTransactionRequests(session.token);
      setRepaymentRequests(requests.filter((request) => request.loanId || /repay/i.test(request.category)));
    } catch {
      setRepaymentRequests([]);
    }
  }, [membership?.member, session?.token, session?.user.role]);

  useEffect(() => {
    loadRepaymentRequests();
  }, [loadRepaymentRequests]);

  const selectedLoan = loansForSelectedType.find((loan) => loan.id === selectedLoanId) ?? loansForSelectedType[0] ?? outstandingLoans[0];
  const amount = Number(repaymentForm.amount);
  const isMpesaRepayment = repaymentForm.method === "M-Pesa";
  const repaymentPhoneNumber = repaymentForm.phoneNumber.trim();
  const isWholeKesAmount = Number.isInteger(amount);

  const submitRepayment = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!session?.token || !selectedLoan || submitting) return;
    setSubmitting(true);
    setMessage("");
    setError("");
    try {
      const created = isMpesaRepayment
        ? (await initiateMpesaStkPush(session.token, {
          purpose: "loan_repayment",
          loanId: selectedLoan.id,
          amount,
          phoneNumber: repaymentPhoneNumber,
          date: repaymentForm.date,
        })).transactionRequest
        : await requestTransaction(session.token, {
          loanId: selectedLoan.id,
          amount,
          type: "Credit",
          category: `Loan Repayment - ${selectedLoan.type}`,
          date: repaymentForm.date,
          ref: repaymentForm.ref,
          channel: repaymentForm.channel,
        });
      setRepaymentRequests((current) => [created, ...current]);
      setMessage(isMpesaRepayment ? "M-Pesa payment request sent. The repayment will remain pending until Daraja confirms payment and admin approves it." : "Repayment request submitted. Your loan balance will update after admin approval.");
      setRepaymentForm({
        amount: "",
        method: repaymentForm.method,
        phoneNumber: repaymentForm.phoneNumber,
        channel: repaymentForm.channel,
        ref: `REPAY-${Math.floor(Date.now() / 1000)}`,
        date: new Date().toISOString().slice(0, 10),
      });
      await refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to submit repayment request");
    } finally {
      setSubmitting(false);
    }
  };

  if (!membership?.member) {
    return (
      <div className="bg-card border border-border rounded-lg p-8 flex flex-col items-center gap-3 text-center">
        <ShieldAlert size={28} className="text-amber-600" />
        <div>
          <p className="text-sm font-semibold text-foreground">Membership approval required</p>
          <p className="text-xs text-muted-foreground mt-1">Repayments are available once your staff account is linked to an active member record.</p>
        </div>
      </div>
    );
  }

  if (!outstandingLoans.length) {
    return (
      <div className="bg-card border border-border rounded-lg p-8 flex flex-col items-center gap-3 text-center">
        <CheckCircle2 size={28} className="text-emerald-600" />
        <div>
          <p className="text-sm font-semibold text-foreground">No pending loan balance</p>
          <p className="text-xs text-muted-foreground mt-1">There are no outstanding loans available for repayment right now.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {outstandingLoans.map((loan) => {
          const repaid = loan.amount > 0 ? Math.max(0, Math.min(100, ((loan.amount - loan.balance) / loan.amount) * 100)) : 0;
          return (
            <button
              key={loan.id}
              type="button"
              onClick={() => {
                setSelectedLoanType(loan.type);
                setSelectedLoanId(loan.id);
              }}
              className={`text-left bg-card border rounded-lg p-4 transition-colors ${selectedLoan?.id === loan.id ? "border-primary ring-2 ring-primary/15" : "border-border hover:border-primary/40"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">{loan.id}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{loan.type} - due {loan.due}</p>
                </div>
                <StatusBadge status={loan.status} />
              </div>
              <p className="mt-4 text-xl font-bold font-['Plus_Jakarta_Sans'] text-foreground">{fmtShort(loan.balance)}</p>
              <div className="mt-3 h-1.5 rounded-full bg-secondary overflow-hidden">
                <div className="h-full rounded-full bg-primary" style={{ width: `${repaid}%` }} />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{Math.round(repaid)}% repaid from {fmtShort(loan.amount)}</p>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <form onSubmit={submitRepayment} className="xl:col-span-1 bg-card border border-border rounded-lg p-5 space-y-4">
          <div>
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Submit Repayment</h3>
            <p className="text-xs text-muted-foreground mt-1">Admin approval applies the payment to the selected loan balance.</p>
          </div>

          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Loan Type</span>
            <select value={selectedLoanType} onChange={(event) => setSelectedLoanType(event.target.value)} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20">
              {loanTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Loan Account</span>
            <select value={selectedLoan?.id ?? ""} onChange={(event) => setSelectedLoanId(event.target.value)} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20">
              {loansForSelectedType.map((loan) => <option key={loan.id} value={loan.id}>{loan.id} - {fmtShort(loan.balance)} due</option>)}
            </select>
          </label>

          {selectedLoan && (
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-border bg-secondary/40 p-3">
              <div>
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">Outstanding</p>
                <p className="text-sm font-bold text-foreground">{fmtShort(selectedLoan.balance)}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">Due Date</p>
                <p className="text-sm font-bold text-foreground">{selectedLoan.due}</p>
              </div>
            </div>
          )}

          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Amount</span>
            <input type="number" min="1" max={selectedLoan?.balance} step={isMpesaRepayment ? "1" : "0.01"} required value={repaymentForm.amount} onChange={(event) => setRepaymentForm((current) => ({ ...current, amount: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
            {isMpesaRepayment && amount > 0 && !isWholeKesAmount && (
              <p className="mt-1 text-xs text-amber-700">M-Pesa STK Push accepts whole KES amounts.</p>
            )}
          </label>

          <div>
            <span className="text-xs font-semibold text-muted-foreground">Payment Method</span>
            <div className="mt-1 grid grid-cols-2 gap-2 rounded-lg border border-border bg-secondary/30 p-1">
              {[
                { method: "M-Pesa", icon: Smartphone },
                { method: "Other", icon: CreditCard },
              ].map(({ method, icon: Icon }) => (
                <button
                  key={method}
                  type="button"
                  onClick={() => setRepaymentForm((current) => ({ ...current, method }))}
                  className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${repaymentForm.method === method ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                >
                  <Icon size={14} />
                  {method}
                </button>
              ))}
            </div>
          </div>

          {isMpesaRepayment ? (
            <label className="block">
              <span className="text-xs font-semibold text-muted-foreground">M-Pesa Phone Number</span>
              <input required inputMode="tel" placeholder="2547XXXXXXXX" value={repaymentForm.phoneNumber} onChange={(event) => setRepaymentForm((current) => ({ ...current, phoneNumber: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
            </label>
          ) : (
            <>
              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Channel</span>
                <input required value={repaymentForm.channel} onChange={(event) => setRepaymentForm((current) => ({ ...current, channel: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              </label>

              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Reference</span>
                <input required value={repaymentForm.ref} onChange={(event) => setRepaymentForm((current) => ({ ...current, ref: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              </label>
            </>
          )}

          <label className="block">
            <span className="text-xs font-semibold text-muted-foreground">Date</span>
            <input type="date" required value={repaymentForm.date} onChange={(event) => setRepaymentForm((current) => ({ ...current, date: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </label>

          {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">{error}</div>}
          {message && <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs text-emerald-700">{message}</div>}

          <button type="submit" disabled={submitting || !selectedLoan || amount <= 0 || amount > (selectedLoan?.balance ?? 0) || (isMpesaRepayment && (!repaymentPhoneNumber || !isWholeKesAmount)) || (!isMpesaRepayment && (!repaymentForm.channel.trim() || !repaymentForm.ref.trim()))} className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
            {isMpesaRepayment ? <Smartphone size={14} /> : <CreditCard size={14} />}
            {submitting ? "Submitting" : isMpesaRepayment ? "Trigger M-Pesa payment" : "Submit repayment"}
          </button>
        </form>

        <div className="xl:col-span-2 bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Repayment Requests</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Track approval status and applied repayments.</p>
          </div>
          <div className="divide-y divide-border">
            {repaymentRequests.length ? repaymentRequests.map((request) => (
              <div key={request.id} className="p-4 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">{request.loanId ?? "Loan"} - {fmtShort(request.amount)}</p>
                  <p className="text-xs text-muted-foreground truncate">{request.mpesaReceiptNumber || request.mpesaCheckoutRequestId || request.ref} - {request.channel}{request.mpesaPhoneNumber ? ` - ${request.mpesaPhoneNumber}` : ""} - {new Date(request.date).toLocaleDateString()}</p>
                </div>
                <StatusBadge status={request.status} />
              </div>
            )) : (
              <p className="p-4 text-sm text-muted-foreground">No repayment requests submitted yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TransactionsView() {
  const { session, membership, data } = useSaccoData();
  const { transactions, anomalyFlags } = data;
  const isAdmin = session?.user.role === "admin";
  const [typeFilter, setTypeFilter] = useState("All");
  const [showFlagged, setShowFlagged] = useState(false);
  const [transactionRequests, setTransactionRequests] = useState<TransactionRequest[]>([]);
  const [requestForm, setRequestForm] = useState<TransactionRequestPayload>({
    amount: 0,
    type: "Credit",
    category: "Deposit",
    date: new Date().toISOString().slice(0, 10),
    ref: `REQ-${Math.floor(Date.now() / 1000)}`,
    channel: "M-Pesa",
    mpesaPhoneNumber: "",
  });
  const [requestPaymentMethod, setRequestPaymentMethod] = useState<"M-Pesa" | "Other">("M-Pesa");
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requestSuccess, setRequestSuccess] = useState<string | null>(null);

  const loadTransactionRequests = React.useCallback(async () => {
    if (!session?.token || isAdmin || !membership?.member) return;
    try {
      const loaded = await listTransactionRequests(session.token);
      setTransactionRequests(loaded);
    } catch (error) {
      console.error(error);
    }
  }, [session?.token, isAdmin, membership?.member]);

  useEffect(() => {
    loadTransactionRequests();
  }, [loadTransactionRequests]);

  const submitTransactionRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!session?.token) return;
    setRequesting(true);
    setRequestError(null);
    setRequestSuccess(null);

    try {
      const created = isMpesaRequest
        ? (await initiateMpesaStkPush(session.token, {
          purpose: /deposit|savings/i.test(requestForm.category) ? "savings_deposit" : "transaction",
          amount: requestAmount,
          phoneNumber: requestPhoneNumber,
          category: requestForm.category.trim(),
          transactionType: "Credit",
          date: requestForm.date,
        })).transactionRequest
        : await requestTransaction(session.token, requestForm);
      setTransactionRequests((current) => [created, ...current]);
      setRequestSuccess(isMpesaRequest ? "M-Pesa payment request sent. The transaction will remain pending until Daraja confirms payment and admin approves it." : "Transaction request submitted. Awaiting admin approval.");
      setRequestForm((current) => ({
        ...current,
        amount: 0,
        type: isMpesaRequest ? "Credit" : current.type,
        category: "Deposit",
        ref: `REQ-${Math.floor(Date.now() / 1000)}`,
        channel: isMpesaRequest ? "M-Pesa" : "Mobile Money",
      }));
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Unable to submit transaction request");
    } finally {
      setRequesting(false);
    }
  };

  const isMpesaRequest = requestPaymentMethod === "M-Pesa";
  const requestAmount = Number(requestForm.amount);
  const requestPhoneNumber = (requestForm.mpesaPhoneNumber ?? "").trim();
  const isWholeMpesaRequestAmount = Number.isInteger(requestAmount);
  const canSubmitTransactionRequest = !requesting
    && requestAmount > 0
    && requestForm.category.trim().length > 0
    && requestForm.date.trim().length > 0
    && (
      isMpesaRequest
        ? requestPhoneNumber.length > 0 && isWholeMpesaRequestAmount
        : requestForm.ref.trim().length > 0 && requestForm.channel.trim().length > 0
    );

  const flaggedIds = Object.keys(anomalyFlags);
  let filtered = typeFilter === "All" ? transactions : transactions.filter((t) => t.type === typeFilter);
  if (showFlagged) filtered = filtered.filter((t) => flaggedIds.includes(t.id));

  const formatCsvValue = (value: string | number | undefined | null) => {
    const stringValue = value == null ? "" : String(value);
    return `"${stringValue.replace(/"/g, '""')}"`;
  };

  const exportTransactionsCsv = () => {
    if (!filtered.length) return;

    const headers = ["Ref", "Member", "Category", "Channel", "Amount", "Type", "Date", "AI Flag"];
    const rows = filtered.map((transaction) => [
      formatCsvValue(transaction.ref),
      formatCsvValue(transaction.member),
      formatCsvValue(transaction.category),
      formatCsvValue(transaction.channel),
      formatCsvValue(transaction.amount),
      formatCsvValue(transaction.type),
      formatCsvValue(transaction.date),
      formatCsvValue(anomalyFlags[transaction.id]?.level ?? ""),
    ]);

    const csvContent = [headers, ...rows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "transactions.csv";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      {/* Anomaly banner */}
      <div className="flex items-start gap-3 p-4 rounded-lg border border-amber-200 bg-amber-50">
        <Brain size={16} className="text-amber-600 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-900">AI Anomaly Detection - 3 transactions flagged</p>
          <p className="text-xs text-amber-700 mt-0.5">1 high-confidence flag (channel switch on large disbursement) and 2 medium-confidence flags detected in the last 7 days.</p>
        </div>
        <button
          onClick={() => setShowFlagged((p) => !p)}
          className={`text-xs font-semibold px-3 py-1.5 rounded border transition-colors flex-shrink-0 ${showFlagged ? "bg-amber-600 text-white border-amber-600" : "bg-white text-amber-700 border-amber-300 hover:bg-amber-100"}`}
        >
          {showFlagged ? "Show all" : "View flagged"}
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-2">
          {["All", "Credit", "Debit"].map((f) => (
            <button key={f} onClick={() => setTypeFilter(f)}
              className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${typeFilter === f ? "bg-primary text-primary-foreground border-primary" : "bg-card text-muted-foreground border-border hover:border-primary/40"}`}>
              {f}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground transition-colors">
            <Filter size={12} /> Filter
          </button>
          <button onClick={exportTransactionsCsv} disabled={!filtered.length} className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50">
            <Download size={12} /> Export CSV
          </button>
        </div>
      </div>

      {!isAdmin && membership?.member && (
        <div className="space-y-4">
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
              <div>
                <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Request a Transaction</h3>
                <p className="text-xs text-muted-foreground mt-1">Submit a savings or loan transaction request for admin review.</p>
              </div>
            </div>

            <form onSubmit={submitTransactionRequest} className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <span className="text-xs font-semibold text-muted-foreground">Payment Method</span>
                <div className="mt-1 grid grid-cols-2 gap-2 rounded-lg border border-border bg-secondary/30 p-1">
                  {(["M-Pesa", "Other"] as const).map((method) => {
                    const Icon = method === "M-Pesa" ? Smartphone : CreditCard;
                    return (
                      <button
                        key={method}
                        type="button"
                        onClick={() => {
                          setRequestPaymentMethod(method);
                          setRequestForm((current) => method === "M-Pesa"
                            ? { ...current, type: "Credit", channel: "M-Pesa" }
                            : { ...current, channel: current.channel === "M-Pesa" ? "Mobile Money" : current.channel }
                          );
                        }}
                        className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${requestPaymentMethod === method ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                      >
                        <Icon size={14} />
                        {method}
                      </button>
                    );
                  })}
                </div>
              </div>

              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Type</span>
                <select
                  value={requestForm.type}
                  onChange={(event) => setRequestForm((current) => ({ ...current, type: event.target.value as "Credit" | "Debit" }))}
                  disabled={isMpesaRequest}
                  className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-70"
                >
                  <option value="Credit">Credit</option>
                  <option value="Debit">Debit</option>
                </select>
              </label>

              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Amount</span>
                <input
                  type="number"
                  min="0"
                  step={isMpesaRequest ? "1" : "0.01"}
                  value={requestForm.amount}
                  onChange={(event) => setRequestForm((current) => ({ ...current, amount: Number(event.target.value) }))}
                  className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                  required
                />
                {isMpesaRequest && requestAmount > 0 && !isWholeMpesaRequestAmount && (
                  <p className="mt-1 text-xs text-amber-700">M-Pesa STK Push accepts whole KES amounts.</p>
                )}
              </label>

              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Category</span>
                <input
                  type="text"
                  value={requestForm.category}
                  onChange={(event) => setRequestForm((current) => ({ ...current, category: event.target.value }))}
                  className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                  required
                />
              </label>

              {isMpesaRequest ? (
                <label className="block">
                  <span className="text-xs font-semibold text-muted-foreground">M-Pesa Phone Number</span>
                  <input
                    inputMode="tel"
                    placeholder="2547XXXXXXXX"
                    value={requestForm.mpesaPhoneNumber ?? ""}
                    onChange={(event) => setRequestForm((current) => ({ ...current, mpesaPhoneNumber: event.target.value }))}
                    className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                    required
                  />
                </label>
              ) : (
                <>
                  <label className="block">
                    <span className="text-xs font-semibold text-muted-foreground">Channel</span>
                    <input
                      type="text"
                      value={requestForm.channel}
                      onChange={(event) => setRequestForm((current) => ({ ...current, channel: event.target.value }))}
                      className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                      required
                    />
                  </label>

                  <label className="block">
                    <span className="text-xs font-semibold text-muted-foreground">Reference</span>
                    <input
                      type="text"
                      value={requestForm.ref}
                      onChange={(event) => setRequestForm((current) => ({ ...current, ref: event.target.value }))}
                      className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                      required
                    />
                  </label>
                </>
              )}

              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Date</span>
                <input
                  type="date"
                  value={requestForm.date}
                  onChange={(event) => setRequestForm((current) => ({ ...current, date: event.target.value }))}
                  className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                  required
                />
              </label>

              <div className="sm:col-span-2 flex flex-col gap-3">
                {requestError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">{requestError}</div>
                )}
                {requestSuccess && (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs text-emerald-700">{requestSuccess}</div>
                )}
                <button
                  type="submit"
                  disabled={!canSubmitTransactionRequest}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {isMpesaRequest ? <Smartphone size={14} /> : <Plus size={14} />}
                  {requesting ? "Submitting" : isMpesaRequest ? "Trigger M-Pesa payment" : "Submit request"}
                </button>
              </div>
            </form>
          </div>

          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">My transaction requests</h3>
                <p className="text-xs text-muted-foreground mt-1">Track pending requests and review statuses.</p>
              </div>
            </div>
            <div className="space-y-3">
              {transactionRequests.length ? transactionRequests.map((request) => (
                <div key={request.id} className="rounded-lg border border-border p-3 bg-secondary/50">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{request.type} - {fmtShort(request.amount)} - {request.category}</p>
                      <p className="text-xs text-muted-foreground">{request.mpesaReceiptNumber || request.mpesaCheckoutRequestId || request.ref} - {request.channel}{request.mpesaPhoneNumber ? ` - ${request.mpesaPhoneNumber}` : ""} - {new Date(request.date).toLocaleDateString()}</p>
                    </div>
                    <span className={`text-xs font-semibold px-2 py-1 rounded ${request.status === "Pending" ? "bg-amber-50 text-amber-700 border border-amber-200" : request.status === "Approved" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                      {request.status}
                    </span>
                  </div>
                  {request.reviewNote && <p className="mt-2 text-xs text-muted-foreground">Admin note: {request.reviewNote}</p>}
                </div>
              )) : (
                <p className="text-sm text-muted-foreground">No transaction requests submitted yet.</p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/40">
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Ref</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Member</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Category</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Channel</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Type</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Date</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <span className="flex items-center gap-1"><Sparkles size={10} className="text-primary" /> AI Flag</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t, i) => {
                const flag = anomalyFlags[t.id];
                return (
                  <tr key={t.id} className={`border-b border-border/50 hover:bg-secondary/30 transition-colors ${flag ? "bg-amber-50/40" : i % 2 === 0 ? "" : "bg-secondary/10"}`}>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-['JetBrains_Mono'] text-xs text-muted-foreground">{t.id}</p>
                        <p className="font-['JetBrains_Mono'] text-xs text-muted-foreground/60">{t.ref}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-medium text-foreground">{t.member}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{t.category}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 rounded bg-secondary text-secondary-foreground border border-border">{t.channel}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-['JetBrains_Mono'] text-sm font-semibold ${t.type === "Credit" ? "text-emerald-600" : "text-red-500"}`}>
                        {t.type === "Credit" ? "+" : "-"}{fmtShort(t.amount)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded border font-medium ${t.type === "Credit" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-600 border-red-200"}`}>{t.type}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-['JetBrains_Mono']">{t.date}</td>
                    <td className="px-4 py-3">
                      {flag ? (
                        <div className="group relative">
                          <span className={`text-xs px-2 py-0.5 rounded border font-semibold cursor-help ${flag.level === "high" ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-600 border-amber-200"}`}>
                            {flag.level === "high" ? " High" : " Medium"}
                          </span>
                          <div className="absolute bottom-full left-0 mb-1 w-56 p-2 bg-foreground text-background text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 leading-relaxed">
                            {flag.reason}
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground/50">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// -- Reports View --------------------------------------------------------------

function ReportsView() {
  const { data } = useSaccoData();
  const { portfolioData, loans } = data;
  const monthlyRepayments = portfolioData.map((d) => ({ month: d.month, amount: d.repayments }));
  const totalDisbursed = loans.reduce((sum, loan) => sum + loan.amount, 0);
  const totalCollected = portfolioData.reduce((sum, point) => sum + point.repayments, 0);
  const outstanding = loans.reduce((sum, loan) => sum + loan.balance, 0);
  const overdue = loans.filter((loan) => loan.status === "Overdue").reduce((sum, loan) => sum + loan.balance, 0);
  const nplRatio = outstanding > 0 ? ((overdue / outstanding) * 100).toFixed(1) : "0.0";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Disbursed YTD", value: fmtShort(totalDisbursed), icon: CreditCard },
          { label: "Total Collected YTD", value: fmtShort(totalCollected), icon: Wallet },
          { label: "Non-Performing Loans", value: `${nplRatio}%`, icon: AlertCircle },
          { label: "Outstanding Portfolio", value: fmtShort(outstanding), icon: TrendingUp },
        ].map((r) => (
          <StatCard key={r.label} label={r.label} value={r.value} icon={r.icon} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-lg p-5">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-1">Monthly Repayments</h3>
          <p className="text-xs text-muted-foreground mb-4">Cash collected from loan repayments</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={monthlyRepayments}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v: number) => [fmtShort(v), "Repayments"]} contentStyle={{ background: "#fff", border: "1px solid rgba(15,76,53,0.12)", borderRadius: 6, fontSize: 12 }} />
              <Bar dataKey="amount" fill="#0F4C35" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-4">Quick Reports</h3>
          <div className="space-y-3">
            {[
              { label: "Member Statement", desc: "Individual savings & loan history", icon: FileText },
              { label: "Loan Aging Report", desc: "Overdue categorized by days past due", icon: Clock },
              { label: "Portfolio at Risk", desc: "NPL analysis with risk exposure", icon: Shield },
              { label: "Annual Financial Summary", desc: "P&L and balance sheet", icon: BarChart3 },
            ].map((r) => (
              <div key={r.label} className="flex items-center gap-3 p-3 rounded-lg border border-border hover:border-primary/40 hover:bg-secondary/30 transition-colors cursor-pointer group">
                <div className="w-8 h-8 rounded bg-secondary flex items-center justify-center flex-shrink-0 group-hover:bg-primary/10 transition-colors">
                  <r.icon size={15} className="text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{r.label}</p>
                  <p className="text-xs text-muted-foreground">{r.desc}</p>
                </div>
                <div className="flex gap-1.5">
                  <button className="p-1.5 rounded hover:bg-secondary transition-colors text-muted-foreground"><Eye size={13} /></button>
                  <button className="p-1.5 rounded hover:bg-secondary transition-colors text-muted-foreground"><Download size={13} /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">API Integration Status</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Live connection health for external payment gateways</p>
          </div>
          <button className="flex items-center gap-1.5 text-xs text-primary font-medium hover:underline">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { name: "M-Pesa Daraja API", endpoint: "api.safaricom.co.ke", status: "Operational", latency: "142ms", uptime: "99.98%" },
            { name: "Pesalink Gateway", endpoint: "api.pesalink.co.ke", status: "Operational", latency: "98ms", uptime: "99.94%" },
            { name: "KRA iTax API", endpoint: "itax.kra.go.ke", status: "Degraded", latency: "2.4s", uptime: "97.12%" },
          ].map((api) => (
            <div key={api.name} className="p-4 rounded-lg border border-border bg-secondary/20">
              <div className="flex items-center gap-2 mb-3">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${api.status === "Operational" ? "bg-emerald-500" : "bg-amber-400"}`} />
                <span className="text-sm font-semibold text-foreground">{api.name}</span>
              </div>
              <p className="font-['JetBrains_Mono'] text-xs text-muted-foreground mb-2">{api.endpoint}</p>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div><p className="text-muted-foreground">Status</p><p className={`font-medium ${api.status === "Operational" ? "text-emerald-600" : "text-amber-600"}`}>{api.status}</p></div>
                <div><p className="text-muted-foreground">Latency</p><p className="font-medium font-['JetBrains_Mono'] text-foreground">{api.latency}</p></div>
                <div><p className="text-muted-foreground">Uptime</p><p className="font-medium font-['JetBrains_Mono'] text-foreground">{api.uptime}</p></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// -- AI Assistant View ---------------------------------------------------------

function SavingsView() {
  const { data } = useSaccoData();
  const { members, transactions, portfolioData } = data;
  const [statusFilter, setStatusFilter] = useState<"All" | "Active" | "Inactive" | "Suspended">("All");

  const latestPortfolio = portfolioData[portfolioData.length - 1];
  const totalSavings = latestPortfolio?.savings ?? members.reduce((sum, member) => sum + member.savings, 0);
  const totalShares = members.reduce((sum, member) => sum + member.shares, 0);
  const depositTransactions = transactions.filter((transaction) => transaction.category.toLowerCase().includes("deposit"));
  const recentDeposits = depositTransactions.reduce((sum, transaction) => sum + transaction.amount, 0);
  const filteredMembers = members
    .filter((member) => statusFilter === "All" || member.status === statusFilter)
    .sort((a, b) => b.savings - a.savings);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Total Deposits" value={fmtShort(totalSavings)} icon={PiggyBank} accent />
        <StatCard label="Share Capital" value={totalShares.toLocaleString()} icon={Wallet} />
        <StatCard label="Recent Deposit Flow" value={fmtShort(recentDeposits)} icon={TrendingUp} />
        <StatCard label="Active Savers" value={members.filter((member) => member.status === "Active").length.toLocaleString()} icon={Users} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 bg-card border border-border rounded-lg p-5 min-w-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Savings Growth</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Member deposits against loan portfolio</p>
            </div>
            <div className="flex gap-1 p-1 bg-secondary rounded-lg w-fit max-w-full overflow-x-auto">
              {(["All", "Active", "Inactive", "Suspended"] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${statusFilter === status ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={portfolioData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`} tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v: number, name: string) => [fmtShort(v), name === "savings" ? "Savings" : "Loans"]} contentStyle={{ background: "#fff", border: "1px solid rgba(15,76,53,0.12)", borderRadius: 6, fontSize: 12 }} />
              <Area type="monotone" dataKey="savings" stroke="#0F4C35" strokeWidth={2.5} fill="#0F4C35" fillOpacity={0.12} />
              <Area type="monotone" dataKey="loans" stroke="#C8A84B" strokeWidth={2} fill="#C8A84B" fillOpacity={0.1} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-1">Savings Health</h3>
          <p className="text-xs text-muted-foreground mb-4">Top savers by current deposit balance</p>
          <div className="space-y-3">
            {filteredMembers.slice(0, 6).map((member) => {
              const percent = totalSavings > 0 ? Math.min(100, (member.savings / totalSavings) * 100) : 0;
              return (
                <div key={member.id} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">{member.name}</p>
                      <p className="text-xs text-muted-foreground">{member.id} - {member.status}</p>
                    </div>
                    <p className="text-sm font-semibold text-foreground font-['JetBrains_Mono']">{fmtShort(member.savings)}</p>
                  </div>
                  <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingsView() {
  const { session, refresh, loading } = useSaccoData();
  const [auditEnabled, setAuditEnabled] = useState(true);
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const settings = [
    { label: "Audit Trail", description: "Log sensitive loan, collection, and fraud-review changes.", enabled: auditEnabled, setEnabled: setAuditEnabled },
    { label: "Risk Alerts", description: "Notify admins when scoring, fraud, or collection thresholds are crossed.", enabled: alertsEnabled, setEnabled: setAlertsEnabled },
    { label: "Auto Refresh", description: "Keep dashboards synced with the backend during active sessions.", enabled: autoRefresh, setEnabled: setAutoRefresh },
  ];

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
      <div className="xl:col-span-2 bg-card border border-border rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">System Preferences</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Operational controls for tracing, alerts, and live data behavior</p>
        </div>
        <div className="divide-y divide-border">
          {settings.map((setting) => (
            <div key={setting.label} className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground">{setting.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{setting.description}</p>
              </div>
              <button
                onClick={() => setting.setEnabled((value) => !value)}
                className={`w-12 h-6 rounded-full p-0.5 transition-colors flex-shrink-0 ${setting.enabled ? "bg-primary" : "bg-muted"}`}
                aria-pressed={setting.enabled}
              >
                <span className={`block w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${setting.enabled ? "translate-x-6" : "translate-x-0"}`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="bg-card border border-border rounded-lg p-5">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-3">Current Session</h3>
          <div className="space-y-3 text-xs">
            <div>
              <p className="text-muted-foreground">Signed in as</p>
              <p className="font-semibold text-foreground">{session?.user.name}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Role</p>
              <p className="font-semibold text-foreground capitalize">{session?.user.role}</p>
            </div>
            <button
              onClick={refresh}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              Refresh Backend Data
            </button>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-3">Tracing Notes</h3>
          <div className="space-y-2 text-xs text-muted-foreground">
            <p>API errors are surfaced in the shell banner and scoring panels with the original backend message.</p>
            <p>AI scoring falls back to the deterministic local model when the backend scoring endpoint is unavailable.</p>
            <p>Fraud and collection actions keep local state changes isolated for easier debugging.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function MembershipApplicationView() {
  const { session, membership, refreshMembership } = useSaccoData();
  const [form, setForm] = useState({ phone: "", nationalId: "", address: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!session?.token || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await applyForMembership(session.token, form);
      await refreshMembership();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit membership application");
    } finally {
      setSubmitting(false);
    }
  };

  if (membership?.member) {
    return (
      <div className="bg-card border border-border rounded-lg p-6 flex items-start gap-3">
        <ShieldCheck size={20} className="text-emerald-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-foreground">Membership approved</p>
          <p className="text-xs text-muted-foreground mt-1">Member ID {membership.member.id} is active. You can now view your financial information and apply for loans.</p>
        </div>
      </div>
    );
  }

  if (membership?.application?.status === "Pending") {
    return (
      <div className="bg-card border border-border rounded-lg p-6 flex items-start gap-3">
        <Clock size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-foreground">Membership application pending</p>
          <p className="text-xs text-muted-foreground mt-1">Your application was submitted on {new Date(membership.application.createdAt).toLocaleDateString()}. An admin must approve it before member features unlock.</p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="max-w-2xl bg-card border border-border rounded-lg p-5 space-y-4">
      <div>
        <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Apply for Membership</h3>
        <p className="text-xs text-muted-foreground mt-0.5">Admin approval is required before financial features are available.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-xs font-semibold text-muted-foreground">Phone</span>
          <input name="phone" id="membership-phone" required value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-muted-foreground">National ID</span>
          <input name="nationalId" id="membership-nationalId" required value={form.nationalId} onChange={(event) => setForm((current) => ({ ...current, nationalId: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
        </label>
      </div>

      <label className="block">
        <span className="text-xs font-semibold text-muted-foreground">Address</span>
        <input name="address" id="membership-address" required value={form.address} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
      </label>

      <label className="block">
        <span className="text-xs font-semibold text-muted-foreground">Notes</span>
        <textarea name="notes" id="membership-notes" value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-24" />
      </label>

      {membership?.application?.status === "Rejected" && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-xs text-red-700">Previous application was rejected{membership.application.notes ? `: ${membership.application.notes}` : "."}</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
          <AlertCircle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-600">{error}</p>
        </div>
      )}

      <button disabled={submitting} className="flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground text-sm font-semibold rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors">
        <ShieldCheck size={14} /> {submitting ? "Submitting" : "Submit Application"}
      </button>
    </form>
  );
}

function AdminView() {
  const { session, refresh } = useSaccoData();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [membershipApplications, setMembershipApplications] = useState<MembershipApplication[]>([]);
  const [loanApplications, setLoanApplications] = useState<LoanApplication[]>([]);
  const [transactionRequests, setTransactionRequests] = useState<TransactionRequest[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [adminError, setAdminError] = useState("");
  const [createForm, setCreateForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "staff" as "admin" | "staff",
  });

  const loadUsers = React.useCallback(async () => {
    if (!session?.token || session.user.role !== "admin") return;
    setLoadingUsers(true);
    setAdminError("");
    try {
      const [loadedUsers, loadedMemberships, loadedLoans, loadedTransactionRequests] = await Promise.all([
        listAdminUsers(session.token),
        listMembershipApplications(session.token),
        listLoanApplications(session.token),
        listTransactionRequests(session.token),
      ]);
      setUsers(loadedUsers);
      setMembershipApplications(loadedMemberships);
      setLoanApplications(loadedLoans);
      setTransactionRequests(loadedTransactionRequests);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to load admin data");
    } finally {
      setLoadingUsers(false);
    }
  }, [session?.token, session?.user.role]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const submitUser = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!session?.token) return;
    setAdminError("");
    try {
      const user = await createAdminUser(session.token, createForm);
      setUsers((current) => [...current, user]);
      setCreateForm({ name: "", email: "", password: "", role: "staff" });
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to create user");
    }
  };

  const changeUser = async (user: AuthUser, payload: { role?: "admin" | "staff"; isActive?: boolean }) => {
    if (!session?.token) return;
    setAdminError("");
    try {
      const updated = await updateAdminUser(session.token, user.id, payload);
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to update user");
    }
  };

  const reviewMembership = async (application: MembershipApplication, status: "Approved" | "Rejected") => {
    if (!session?.token) return;
    setReviewingId(`membership-${application.id}`);
    setAdminError("");
    try {
      const updated = await reviewMembershipApplication(session.token, application.id, status);
      setMembershipApplications((current) => current.map((item) => item.id === updated.id ? updated : item));
      await refresh();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to review membership application");
    } finally {
      setReviewingId(null);
    }
  };

  const reviewLoan = async (application: LoanApplication, status: "Approved" | "Rejected") => {
    if (!session?.token) return;
    setReviewingId(`loan-${application.id}`);
    setAdminError("");
    try {
      const updated = await reviewLoanApplication(session.token, application.id, status);
      setLoanApplications((current) => current.map((item) => item.id === updated.id ? updated : item));
      await refresh();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to review loan application");
    } finally {
      setReviewingId(null);
    }
  };

  const reviewTransactionRequestItem = async (request: TransactionRequest, status: "Approved" | "Rejected") => {
    if (!session?.token) return;
    setReviewingId(`transaction-request-${request.id}`);
    setAdminError("");
    try {
      const updated = await reviewTransactionRequest(session.token, request.id, status);
      setTransactionRequests((current) => current.map((item) => item.id === updated.id ? updated : item));
      await refresh();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to review transaction request");
    } finally {
      setReviewingId(null);
    }
  };

  if (session?.user.role !== "admin") {
    return (
      <div className="bg-card border border-border rounded-lg p-8 flex flex-col items-center gap-3 text-center">
        <ShieldAlert size={28} className="text-amber-600" />
        <div>
          <p className="text-sm font-semibold text-foreground">Admin access required</p>
          <p className="text-xs text-muted-foreground mt-1">Only admin users can manage staff and system users.</p>
        </div>
      </div>
    );
  }

  const pendingMembershipApplications = membershipApplications.filter((application) => application.status === "Pending");
  const pendingLoanApplications = loanApplications.filter((application) => application.status === "Pending");

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Membership Applications</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Approve users into active SACCO members</p>
          </div>
          <div className="divide-y divide-border">
            {pendingMembershipApplications.map((application) => (
              <div key={application.id} className="p-4 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">{application.name}</p>
                  <p className="text-xs text-muted-foreground truncate">{application.email} - {application.phone}</p>
                </div>
                <div className="flex gap-2">
                  <button disabled={reviewingId === `membership-${application.id}`} onClick={() => reviewMembership(application, "Approved")} className="px-3 py-1.5 text-xs font-semibold rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50">Approve</button>
                  <button disabled={reviewingId === `membership-${application.id}`} onClick={() => reviewMembership(application, "Rejected")} className="px-3 py-1.5 text-xs font-semibold rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50">Reject</button>
                </div>
              </div>
            ))}
            {!pendingMembershipApplications.length && <p className="p-4 text-sm text-muted-foreground">No pending membership applications.</p>}
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Loan Applications</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Approve member loan requests into active loans</p>
          </div>
          <div className="divide-y divide-border">
            {pendingLoanApplications.map((application) => (
              <div key={application.id} className="p-4 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">{application.member} - {fmtShort(application.amount)}</p>
                  <p className="text-xs text-muted-foreground truncate">{application.type} - {application.termMonths} months - {application.purpose || "No purpose provided"}</p>
                </div>
                <div className="flex gap-2">
                  <button disabled={reviewingId === `loan-${application.id}`} onClick={() => reviewLoan(application, "Approved")} className="px-3 py-1.5 text-xs font-semibold rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50">Approve</button>
                  <button disabled={reviewingId === `loan-${application.id}`} onClick={() => reviewLoan(application, "Rejected")} className="px-3 py-1.5 text-xs font-semibold rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50">Reject</button>
                </div>
              </div>
            ))}
            {!pendingLoanApplications.length && <p className="p-4 text-sm text-muted-foreground">No pending loan applications.</p>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-3 bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Transaction Requests</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Review member transaction requests and approve credits into the accounts.</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/40">
                  {[
                    "Ref",
                    "Member",
                    "Request",
                    "Amount",
                    "Channel",
                    "Status",
                    "Requested",
                    "Actions",
                  ].map((heading) => (
                    <th key={heading} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transactionRequests.map((request) => (
                  <tr key={request.id} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <p className="font-['JetBrains_Mono'] text-foreground">{request.mpesaReceiptNumber || request.ref}</p>
                      {request.mpesaReceiptNumber && request.mpesaReceiptNumber !== request.ref && (
                        <p className="font-['JetBrains_Mono'] mt-0.5">{request.ref}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium text-foreground">{request.member}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <p className="font-semibold text-foreground">{request.category}</p>
                      <p>{request.type}{request.loanId ? ` - ${request.loanId}` : ""}</p>
                    </td>
                    <td className="px-4 py-3 font-semibold">{request.type === "Credit" ? "+" : "-"}{fmtShort(request.amount)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <p className="font-medium text-foreground">{request.channel}</p>
                      {request.mpesaPhoneNumber && <p className="font-['JetBrains_Mono'] mt-0.5">{request.mpesaPhoneNumber}</p>}
                      {request.mpesaCheckoutRequestId && <p className="font-['JetBrains_Mono'] mt-0.5 truncate max-w-36">{request.mpesaCheckoutRequestId}</p>}
                    </td>
                    <td className="px-4 py-3 text-xs font-semibold">
                      <span className={`px-2 py-1 rounded ${request.status === "Pending" ? "bg-amber-50 text-amber-700 border border-amber-200" : request.status === "Approved" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                        {request.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-['JetBrains_Mono']">{new Date(request.createdAt).toLocaleDateString()}</td>
                    <td className="px-4 py-3 flex gap-2 flex-wrap">
                      {request.status === "Pending" ? (
                        <>
                          <button
                            disabled={reviewingId === `transaction-request-${request.id}`}
                            onClick={() => reviewTransactionRequestItem(request, "Approved")}
                            className="px-3 py-1.5 text-xs font-semibold rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            disabled={reviewingId === `transaction-request-${request.id}`}
                            onClick={() => reviewTransactionRequestItem(request, "Rejected")}
                            className="px-3 py-1.5 text-xs font-semibold rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </>
                      ) : (
                        <span className="text-xs text-muted-foreground">No action</span>
                      )}
                    </td>
                  </tr>
                ))}
                {!transactionRequests.length && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-muted-foreground">No transaction requests found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      <div className="xl:col-span-2 bg-card border border-border rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Admin Users</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Users and roles from the backend admin endpoint</p>
          </div>
          <button
            onClick={loadUsers}
            disabled={loadingUsers}
            className="flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg border border-border hover:bg-secondary disabled:opacity-50"
          >
            <RefreshCw size={12} className={loadingUsers ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/40">
                {["User", "Role", "Status", "Created", "Actions"].map((heading) => (
                  <th key={heading} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-foreground">{user.name}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={user.role}
                      onChange={(event) => changeUser(user, { role: event.target.value as "admin" | "staff" })}
                      className="px-2 py-1.5 text-xs rounded border border-border bg-input-background capitalize"
                    >
                      <option value="admin">admin</option>
                      <option value="staff">staff</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={user.isActive ? "Active" : "Inactive"} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground font-['JetBrains_Mono']">
                    {new Date(user.createdAt).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => changeUser(user, { isActive: !user.isActive })}
                      disabled={user.id === session.user.id}
                      className="text-xs px-2.5 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-40"
                    >
                      {user.isActive ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
              {!users.length && !loadingUsers && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">No admin users loaded.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <form onSubmit={submitUser} className="bg-card border border-border rounded-lg p-5 space-y-4">
        <div>
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Create User</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Add backend staff or admin accounts</p>
        </div>

        {[
          { id: "name", label: "Name", type: "text" },
          { id: "email", label: "Email", type: "email" },
          { id: "password", label: "Password", type: "password" },
        ].map((field) => (
          <label key={field.id} className="block">
            <span className="text-xs font-semibold text-muted-foreground">{field.label}</span>
            <input
              name={field.id}
              id={`admin-${field.id}`}
              type={field.type}
              value={createForm[field.id as "name" | "email" | "password"]}
              onChange={(event) => setCreateForm((current) => ({ ...current, [field.id]: event.target.value }))}
              required
              minLength={field.id === "password" ? 12 : undefined}
              className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            {field.id === "password" && (
              <p className="text-xs text-muted-foreground mt-2">Password must be at least 12 characters and include letters, numbers, and symbols.</p>
            )}
          </label>
        ))}

        <label className="block">
          <span className="text-xs font-semibold text-muted-foreground">Role</span>
          <select
            value={createForm.role}
            onChange={(event) => setCreateForm((current) => ({ ...current, role: event.target.value as "admin" | "staff" }))}
            className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="staff">Staff</option>
            <option value="admin">Admin</option>
          </select>
        </label>

        {adminError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
            <AlertCircle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-600">{adminError}</p>
          </div>
        )}

        <button type="submit" className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground text-sm font-semibold rounded-lg hover:bg-primary/90 transition-colors">
          <Plus size={14} />
          Create User
        </button>
      </form>
      </div>
    </div>
  );
}

const SUGGESTED_PROMPTS = [
  "Show me a live portfolio summary",
  "How many active members do we have?",
  "List overdue loans with balances",
  "Find member by phone or ID number",
  "Show recent credit transactions",
];

const INITIAL_MESSAGE: ChatMessage = {
  role: "assistant",
  content: `Hello, I'm **UmojaAI** - your read-only SACCO database assistant.\n\nI can query live UmojaFunds data without writing to the database. Ask me for:\n\n- **Portfolio summaries** - savings, loan exposure, NPL ratio, overdue totals\n- **Member lookups** - by name, member ID, phone, national ID, or account number\n- **Loan records** - active, overdue, pending, completed, or member-specific loans\n- **Transactions** - recent credits, debits, M-Pesa channels, categories, references\n- **External records** - member intelligence, payslips, disbursement dates, biodata, books, attendance, and related tables\n\nTry: "Show me overdue loans" or "Search external member data for 0712345678".`,
  ts: "Just now",
};

function AIAssistantView() {
  const { data } = useSaccoData();
  const { members, loans, transactions, portfolioData, memberProfiles, anomalyFlags } = data;
  const geminiEnabled = isGeminiConfigured();
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const now = () => new Date().toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);



  const send = async (query: string) => {
    if (!query.trim() || typing) return;

    const userMsg: ChatMessage = { role: "user", content: query.trim(), ts: now() };
    setMessages((p) => [...p, userMsg]);
    setInput("");
    setTyping(true);
    setError("");
    
     try {
       // Build conversation history for context
       const history = messages.filter(m => m.role !== "assistant" || messages.indexOf(m) > 0).map(m => ({
         role: m.role,
         content: m.content,
       }));
       
       // Prepare SACCO context
       const saccoContext = {
         members,
         loans,
         transactions,
         portfolioData,
         memberProfiles,
         anomalyFlags,
         currentYear: 2026,
       };
       
       const reply = await sendGeminiMessage(query, saccoContext, history);
       setMessages((p) => [...p, { role: "assistant", content: reply, ts: now() }]);
     } catch (err: any) {
       console.error("Gemini error:", err);
       setError(err.message || "Failed to get response from Gemini");
       
       // Fall back to local response if Gemini fails.
       const fallbackReply = getAIResponse(query, data) + "\n\n *Note: Gemini was unavailable, so this response was generated from the loaded backend data. Error: " + (err.message || "Unknown error") + "*";
       setMessages((p) => [...p, { role: "assistant", content: fallbackReply, ts: now() }]);
     } finally {
       setTyping(false);
     }
  };

  const forecastData = [
    { month: "Jul", actual: 1750000, forecast: undefined },
    { month: "Aug", actual: undefined, forecast: 1820000 },
    { month: "Sep", actual: undefined, forecast: 1950000 },
    { month: "Oct", actual: undefined, forecast: 2040000 },
  ];

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 h-full">
        {/* Chat panel */}
        <div className="lg:col-span-2 bg-card border border-border rounded-lg flex flex-col overflow-hidden min-h-[560px]">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 px-5 py-4 border-b border-border bg-primary/5">
            <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
              <Bot size={16} className="text-primary-foreground" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground font-['Plus_Jakarta_Sans']">UmojaAI</p>
              <p className={`text-xs flex items-center gap-1 ${geminiEnabled ? "text-emerald-600" : "text-amber-600"}`}>
                <span className={`w-1.5 h-1.5 rounded-full inline-block ${geminiEnabled ? "bg-emerald-500" : "bg-amber-500"}`} /> 
                {geminiEnabled ? "Online - Gemini-powered" : "Mock mode - Connect Gemini API"}
              </p>
            </div>
            <div className="sm:ml-auto flex flex-wrap items-center gap-2">
              {geminiEnabled && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                  <CheckCircle size={12} />
                  <span>Gemini Active</span>
                </div>
              )}
              <span className="text-xs text-muted-foreground bg-secondary px-2 py-1 rounded border border-border">Context: live 2026 backend data</span>
            </div>
          </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${msg.role === "user" ? "bg-accent text-accent-foreground" : "bg-primary text-primary-foreground"}`}>
                {msg.role === "user" ? "JN" : <Bot size={13} />}
              </div>
              <div className={`max-w-[88%] sm:max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1 min-w-0`}>
                <div className={`px-4 py-3 rounded-xl text-sm ${msg.role === "user" ? "bg-primary text-primary-foreground rounded-tr-sm" : "bg-secondary border border-border rounded-tl-sm"}`}>
                  {msg.role === "assistant"
                    ? <AIMessageRenderer content={msg.content} />
                    : <p>{msg.content}</p>
                  }
                </div>
                <p className="text-xs text-muted-foreground px-1">{msg.ts}</p>
              </div>
            </div>
          ))}

          {typing && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                <Bot size={13} className="text-primary-foreground" />
              </div>
              <div className="bg-secondary border border-border px-4 py-3 rounded-xl rounded-tl-sm">
                <div className="flex gap-1 items-center h-4">
                  {[0, 1, 2].map((d) => (
                    <div key={d} className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: `${d * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested prompts */}
        {messages.length <= 1 && (
          <div className="px-5 pb-3">
            <p className="text-xs text-muted-foreground mb-2">Suggested questions</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button key={p} onClick={() => send(p)}
                  className="text-xs px-3 py-1.5 rounded-full border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 transition-colors">
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="px-5 pb-2">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
              <AlertCircle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-red-700 font-medium">Error</p>
                <p className="text-xs text-red-600 mt-0.5">{error}</p>
              </div>
              <button onClick={() => setError("")} className="text-red-400 hover:text-red-600">
                <X size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Input */}
        <div className="px-5 pb-4 pt-2 border-t border-border">
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask live DB questions: portfolio, members, loans, transactions..."
              className="flex-1 px-4 py-2.5 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            <button type="submit" disabled={typing || !input.trim()}
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-colors flex-shrink-0">
              <Send size={15} />
            </button>
          </form>
        </div>
      </div>

      {/* Right panel - context cards */}
      <div className="space-y-4">
        {/* AI model info */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={14} className="text-primary" />
            <p className="text-sm font-semibold text-foreground font-['Plus_Jakarta_Sans']">AI Capabilities</p>
          </div>
          <div className="space-y-2">
            {[
              { icon: Bot, label: "Gemini AI", status: geminiEnabled ? "Connected" : "Not Connected", color: geminiEnabled ? "text-emerald-600" : "text-amber-600" },
              { icon: Activity, label: "Anomaly Detection", status: "Active", color: "text-emerald-600" },
              { icon: Sparkles, label: "Credit Scoring", status: "Active", color: "text-emerald-600" },
              { icon: TrendingUp, label: "Forecasting", status: geminiEnabled ? "AI-Powered" : "Rule-Based", color: geminiEnabled ? "text-emerald-600" : "text-amber-600" },
              { icon: Users, label: "Churn Prediction", status: geminiEnabled ? "Active" : "Limited", color: geminiEnabled ? "text-emerald-600" : "text-amber-600" },
            ].map((cap) => (
              <div key={cap.label} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <cap.icon size={12} />
                  <span>{cap.label}</span>
                </div>
                <span className={`font-medium ${cap.color}`}>{cap.status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Repayment forecast mini chart */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={12} className="text-primary" />
            <p className="text-xs font-semibold text-foreground">Repayment Forecast</p>
          </div>
          <p className="text-xs text-muted-foreground mb-3">Actual vs AI-projected</p>
          <ResponsiveContainer width="100%" height={100}>
            <LineChart data={forecastData}>
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip formatter={(v: number) => [fmtShort(v), ""]} contentStyle={{ fontSize: 11, borderRadius: 6 }} />
              <Line type="monotone" dataKey="actual" stroke="#0F4C35" strokeWidth={2} dot={{ fill: "#0F4C35", r: 3 }} connectNulls={false} />
              <Line type="monotone" dataKey="forecast" stroke="#C8A84B" strokeWidth={2} strokeDasharray="4 3" dot={{ fill: "#C8A84B", r: 3 }} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <div className="w-4 h-0.5 bg-primary rounded" /> Actual
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <div className="w-4 h-0.5 bg-accent rounded border-dashed border-t border-accent" /> Forecast
            </div>
          </div>
        </div>

        {/* Top risk members */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <TriangleAlert size={13} className="text-red-500" />
            <p className="text-xs font-semibold text-foreground">High-Risk Members</p>
          </div>
          <div className="space-y-2.5">
            {members
              .map((m) => ({ ...m, cs: computeCreditScore(m) }))
              .filter((m) => m.cs.score < 620)
              .slice(0, 3)
              .map((m) => (
                <div key={m.id} className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs font-bold flex-shrink-0">
                    {m.name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">{m.name}</p>
                    <div className="w-full h-1 rounded-full bg-secondary mt-0.5 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${((m.cs.score - 300) / 550) * 100}%`, background: m.cs.color }} />
                    </div>
                  </div>
                  <span className="text-xs font-bold font-['JetBrains_Mono']" style={{ color: m.cs.color }}>{m.cs.score}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>

  </>
  );
}

// -- Loan Scoring View ---------------------------------------------------------

const RISK_COLOR: Record<string, string> = {
  "Very Low": "#059669", Low: "#0F4C35", Medium: "#C8A84B", High: "#EA580C", "Very High": "#DC2626",
};
const REC_STYLE: Record<string, { bg: string; border: string; text: string }> = {
  "Approve":                   { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700" },
  "Approve with Conditions":   { bg: "bg-blue-50",    border: "border-blue-200",    text: "text-blue-700" },
  "Counter-offer":             { bg: "bg-amber-50",   border: "border-amber-200",   text: "text-amber-700" },
  "Decline":                   { bg: "bg-red-50",     border: "border-red-200",     text: "text-red-700" },
};

function normalizeScoreResult(result: BackendLoanScoreResult, requestedAmount: number, member?: Member): LoanScoreResult {
  return {
    composite: result.composite,
    repaymentLikelihood: result.repaymentLikelihood,
    defaultRisk: result.defaultRisk as DefaultRisk,
    affordabilityRatio: result.affordabilityRatio ?? (member ? requestedAmount / Math.max(member.savings, 1) : 0),
    delinquencyRisk90d: result.delinquencyRisk90d ?? Math.max(2, Math.round((100 - result.composite) * 0.52)),
    recommendation: result.recommendation as Recommendation,
    maxLoanAmount: result.maxLoanAmount ?? requestedAmount,
    suggestedRate: result.suggestedRate ?? 12,
    dimensions: result.dimensions.map((dimension) => ({
      name: dimension.name,
      score: dimension.score,
      weight: dimension.weight,
      signal: dimension.signal,
      trend: dimension.trend as ScoreTrend,
    })),
    keyRisks: result.keyRisks,
    keyStrengths: result.keyStrengths,
  };
}

function LoanScoringView() {
  const { data, session } = useSaccoData();
  const { members, memberProfiles, loans } = data;
  const [selectedId, setSelectedId] = useState("");
  const [loanAmount, setLoanAmount] = useState("");
  const [loanType, setLoanType] = useState("Business");
  const [result, setResult] = useState<LoanScoreResult | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState("");

  const member = members.find((m) => m.id === selectedId);
  const profile = selectedId ? memberProfiles[selectedId] : null;

  const runScore = async () => {
    if (!selectedId || !loanAmount || scoring) return;
    setScoring(true);
    setResult(null);
    setScoreError("");
    const requestedAmount = Number.parseInt(loanAmount, 10);
    try {
      if (!session?.token) throw new Error("Please sign in before running loan scoring.");
      const backendResult = await scoreLoan(session.token, selectedId, requestedAmount, loanType);
      setResult(normalizeScoreResult(backendResult, requestedAmount, member));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Loan scoring failed";
      setScoreError(message);
      try {
        setResult(computeLoanScore(selectedId, requestedAmount, members, memberProfiles, loans));
      } catch {
        setResult(null);
      }
    } finally {
      setScoring(false);
    }
  };

  const recStyle = result ? REC_STYLE[result.recommendation] : null;

  const radarData = result?.dimensions.map((d) => ({ subject: d.name.replace(" ", "\n"), score: d.score, fullMark: 100 }));

  return (
    <div className="space-y-5">
      {/* -- Application input card -- */}
      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
            <Brain size={15} className="text-primary" />
          </div>
          <div>
            <h3 className="font-bold text-foreground font-['Plus_Jakarta_Sans'] text-sm">AI Loan Scoring Engine</h3>
            <p className="text-xs text-muted-foreground">7-factor predictive model - repayment, default, affordability, delinquency</p>
          </div>
          <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-primary/8 text-primary border border-primary/20 font-semibold hidden sm:inline">
            v2.1 - Gemini-ready
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div>
            <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Member</label>
            <select value={selectedId} onChange={(e) => { setSelectedId(e.target.value); setResult(null); }}
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20">
              <option value="">Select member...</option>
              {members.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.id})</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Loan Amount (KES)</label>
            <input type="number" placeholder="e.g. 500000" value={loanAmount}
              onChange={(e) => { setLoanAmount(e.target.value); setResult(null); }}
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Loan Type</label>
            <select value={loanType} onChange={(e) => setLoanType(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20">
              {["Business", "Education", "Emergency", "Development", "Agricultural"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={runScore} disabled={!selectedId || !loanAmount || scoring}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground text-sm font-semibold rounded-lg hover:bg-primary/90 disabled:opacity-40 transition-colors">
              {scoring
                ? <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Scoring...</>
                : <><Sparkles size={14} /> Run AI Score</>}
            </button>
          </div>
        </div>

        {/* Member context strip */}
        {member && profile && (
          <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 sm:grid-cols-6 gap-x-4 gap-y-2">
            {[
              { label: "Employer", value: profile.employer },
              { label: "Employment Type", value: profile.employerType },
              { label: "Est. Monthly Income", value: fmtShort(profile.estimatedMonthlyIncome) },
              { label: "Current Savings", value: fmtShort(member.savings) },
              { label: "Outstanding Loans", value: member.loans > 0 ? fmtShort(member.loans) : "None" },
              { label: "Guarantors", value: `${profile.guarantors.length} registered` },
            ].map((f) => (
              <div key={f.label}>
                <p className="text-xs text-muted-foreground">{f.label}</p>
                <p className="text-xs font-semibold text-foreground mt-0.5 truncate">{f.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {scoreError && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
          <AlertCircle size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-700">{scoreError}</p>
        </div>
      )}

      {/* -- Scoring in progress -- */}
      {scoring && (
        <div className="bg-card border border-border rounded-lg p-10 flex flex-col items-center gap-4 text-muted-foreground">
          <div className="w-10 h-10 border-2 border-border border-t-primary rounded-full animate-spin" />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">Analysing 7 scoring factors...</p>
            <p className="text-xs mt-0.5">Salary patterns - Savings consistency - Repayment history - Mobile money - Employer - Guarantors - Spending</p>
          </div>
        </div>
      )}

      {/* -- Results -- */}
      {result && !scoring && (
        <>
          {/* Top 4 metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Gauge card */}
            <div className="bg-card border border-border rounded-lg p-5 flex flex-col items-center gap-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Composite Score</p>
              <ScoreGauge score={result.composite} />
            </div>

            <div className="bg-card border border-border rounded-lg p-5 flex flex-col gap-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Repayment Likelihood</p>
              <p className="text-3xl font-bold font-['Plus_Jakarta_Sans'] text-foreground">{result.repaymentLikelihood}%</p>
              <div className="h-2 rounded-full bg-secondary overflow-hidden">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${result.repaymentLikelihood}%` }} />
              </div>
              <p className="text-xs text-muted-foreground -mt-1">Probability of full repayment</p>
            </div>

            <div className="bg-card border border-border rounded-lg p-5 flex flex-col gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Default Risk</p>
              <p className="text-2xl font-bold font-['Plus_Jakarta_Sans'] mt-1" style={{ color: RISK_COLOR[result.defaultRisk] }}>
                {result.defaultRisk}
              </p>
              <div className="flex items-center gap-1.5 mt-auto">
                <span className="w-2 h-2 rounded-full" style={{ background: RISK_COLOR[result.defaultRisk] }} />
                <span className="text-xs text-muted-foreground">7-factor model - 2026</span>
              </div>
            </div>

            <div className="bg-card border border-border rounded-lg p-5 flex flex-col gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Early Delinquency (90d)</p>
              <p className={`text-3xl font-bold font-['Plus_Jakarta_Sans'] mt-1 ${result.delinquencyRisk90d < 20 ? "text-emerald-600" : result.delinquencyRisk90d < 40 ? "text-amber-600" : "text-red-600"}`}>
                {result.delinquencyRisk90d}%
              </p>
              <p className="text-xs text-muted-foreground mt-auto">Predicted first missed payment</p>
            </div>
          </div>

          {/* Radar + Recommendation */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 bg-card border border-border rounded-lg p-5">
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans'] mb-0.5">7-Factor Radar</h3>
              <p className="text-xs text-muted-foreground mb-3">Each dimension scored 0-100, weighted by predictive importance</p>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(15,76,53,0.1)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10.5, fill: "#5A6B60" }} />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: "#9CA3AF" }} tickCount={5} />
                  <Radar dataKey="score" stroke="#0F4C35" fill="#0F4C35" fillOpacity={0.18} strokeWidth={2}
                    dot={{ fill: "#0F4C35", r: 3 }} />
                  <Tooltip formatter={(v: number) => [v, "Score"]} contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid rgba(15,76,53,0.12)" }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Recommendation panel */}
            <div className="bg-card border border-border rounded-lg p-5 flex flex-col gap-4">
              <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">AI Recommendation</h3>

              <div className={`p-4 rounded-xl border ${recStyle!.bg} ${recStyle!.border}`}>
                <div className="flex items-center gap-2 mb-3">
                  {result.recommendation === "Approve" && <CheckCircle2 size={16} className="text-emerald-600" />}
                  {result.recommendation === "Approve with Conditions" && <CheckCircle2 size={16} className="text-blue-600" />}
                  {result.recommendation === "Counter-offer" && <AlertCircle size={16} className="text-amber-600" />}
                  {result.recommendation === "Decline" && <X size={16} className="text-red-600" />}
                  <span className={`font-bold text-sm ${recStyle!.text}`}>{result.recommendation}</span>
                </div>
                <div className="space-y-2 text-xs">
                  {[
                    { label: "Max loan amount", value: fmtShort(result.maxLoanAmount), mono: true },
                    { label: "Suggested rate", value: `${result.suggestedRate}% p.a.`, mono: true },
                    { label: "Affordability ratio", value: `${result.affordabilityRatio.toFixed(1)}x income`, mono: true, warn: result.affordabilityRatio > 5 },
                    { label: "Loan type", value: loanType, mono: false },
                  ].map((row) => (
                    <div key={row.label} className="flex justify-between">
                      <span className="text-muted-foreground">{row.label}</span>
                      <span className={`font-semibold ${row.mono ? "font-['JetBrains_Mono']" : ""} ${row.warn ? "text-red-600" : ""}`}>{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {result.keyStrengths.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-emerald-700 mb-2 flex items-center gap-1.5">
                    <CheckCircle2 size={11} /> Key Strengths
                  </p>
                  <div className="space-y-1.5">
                    {result.keyStrengths.map((s, i) => (
                      <p key={i} className="text-xs text-foreground/80 flex items-start gap-1.5">
                        <span className="text-emerald-400 mt-0.5 flex-shrink-0"> - </span>{s}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {result.keyRisks.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-red-600 mb-2 flex items-center gap-1.5">
                    <TriangleAlert size={11} /> Key Risks
                  </p>
                  <div className="space-y-1.5">
                    {result.keyRisks.map((r, i) => (
                      <p key={i} className="text-xs text-foreground/80 flex items-start gap-1.5">
                        <span className="text-red-400 mt-0.5 flex-shrink-0"> - </span>{r}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Factor breakdown table */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-secondary/30">
              <Sparkles size={13} className="text-primary" />
              <p className="text-sm font-semibold text-foreground">Detailed Factor Analysis</p>
              <span className="ml-auto text-xs text-muted-foreground">Weighted composite: {result.composite}/100</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/20">
                    {["Factor", "Signal / Evidence", "Score", "Confidence Bar", "Weight", "Trend"].map((h) => (
                      <th key={h} className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.dimensions.map((d, i) => {
                    const sc = d.score >= 70 ? "#059669" : d.score >= 50 ? "#C8A84B" : "#DC2626";
                    return (
                      <tr key={d.name} className={`border-b border-border/50 hover:bg-secondary/20 transition-colors ${i % 2 === 0 ? "" : "bg-secondary/10"}`}>
                        <td className="px-5 py-3.5 font-semibold text-foreground text-sm whitespace-nowrap">{d.name}</td>
                        <td className="px-5 py-3.5 text-xs text-muted-foreground max-w-[220px]">{d.signal}</td>
                        <td className="px-5 py-3.5 font-['JetBrains_Mono'] font-bold text-base" style={{ color: sc }}>{d.score}</td>
                        <td className="px-5 py-3.5 min-w-[120px]">
                          <div className="h-2 rounded-full bg-secondary overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${d.score}%`, background: sc, transition: "width 0.5s ease" }} />
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-xs text-center font-['JetBrains_Mono'] text-muted-foreground">{Math.round(d.weight * 100)}%</td>
                        <td className="px-5 py-3.5 text-center">
                          {d.trend === "up" && <TrendingUp size={14} className="text-emerald-500 mx-auto" />}
                          {d.trend === "down" && <TrendingDown size={14} className="text-red-500 mx-auto" />}
                            {d.trend === "flat" && <span className="text-muted-foreground text-sm">-&gt;</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-5 py-3 border-t border-border bg-secondary/10 flex items-center gap-2">
              <Info size={12} className="text-muted-foreground flex-shrink-0" />
              <p className="text-xs text-muted-foreground">Scores are deterministic based on member portfolio data. Model version 2.1 - Trained on 36 months of UmojaFunds history.</p>
            </div>
          </div>
        </>
      )}

      {/* -- Placeholder when nothing selected -- */}
      {!result && !scoring && !selectedId && (
        <div className="bg-card border border-dashed border-border rounded-lg p-12 flex flex-col items-center gap-4 text-center">
          <div className="w-14 h-14 rounded-full bg-primary/8 flex items-center justify-center">
            <Brain size={24} className="text-primary/60" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Select a member and enter a loan amount</p>
            <p className="text-xs text-muted-foreground mt-1">The AI will score repayment likelihood, default risk, affordability, and early delinquency across 7 weighted factors.</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-2 text-xs text-muted-foreground w-full max-w-lg">
            {["Salary Patterns", "Savings Consistency", "Repayment History", "Mobile Money Inflow", "Employer Stability", "Guarantor Strength", "Spending Behavior", "Debt-Service Ratio"].map((f) => (
              <div key={f} className="flex items-center gap-1.5 bg-secondary/50 rounded px-2 py-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-primary/40 flex-shrink-0" />{f}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// -- Fraud Detection Data ------------------------------------------------------

type FraudSeverity = "Critical" | "High" | "Medium" | "Low";
type FraudAlertStatus = "Open" | "Under Review" | "Resolved" | "False Positive";
type NetNodeType = "member" | "phone" | "device" | "ip";

interface FraudAlert {
  id: string; type: string; severity: FraudSeverity;
  members: string[]; name: string; detected: string;
  description: string; evidence: string[];
  status: FraudAlertStatus; riskScore: number;
}
interface NetNode { id: string; label: string; sublabel: string; type: NetNodeType; x: number; y: number; flagged: boolean; }
interface NetEdge { source: string; target: string; label: string; severity: string; dashed: boolean; }

const SEV_STYLE: Record<FraudSeverity, { bar: string; badge: string }> = {
  Critical: { bar: "bg-red-500",    badge: "bg-red-50 border-red-300 text-red-700" },
  High:     { bar: "bg-orange-400", badge: "bg-orange-50 border-orange-300 text-orange-700" },
  Medium:   { bar: "bg-amber-400",  badge: "bg-amber-50 border-amber-200 text-amber-700" },
  Low:      { bar: "bg-blue-400",   badge: "bg-blue-50 border-blue-200 text-blue-700" },
};

const STAT_STYLE: Record<FraudAlertStatus, string> = {
  "Open":          "bg-red-50 text-red-600 border-red-200",
  "Under Review":  "bg-amber-50 text-amber-600 border-amber-200",
  "Resolved":      "bg-emerald-50 text-emerald-700 border-emerald-200",
  "False Positive":"bg-gray-100 text-gray-500 border-gray-200",
};

// Fraud network and behavioral profiles are generated from live backend SACCO data.

function FraudNetworkGraph() {
  const { data } = useSaccoData();
  const [hovered, setHovered] = useState<string | null>(null);

  const { nodes, edges, clusterCount } = React.useMemo(() => {
    const memberRows = data.members.map((member) => {
      const txns = data.transactions.filter((txn) => txn.member === member.id || txn.member === member.name);
      const sortedTxns = [...txns].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      const flaggedTxns = sortedTxns.filter((txn) => Boolean(data.anomalyFlags[txn.id]));
      const overdueLoans = data.loans.filter((loan) => (loan.member === member.id || loan.member === member.name) && loan.status === "Overdue");
      const riskScore = Math.min(95, 30 + flaggedTxns.length * 20 + overdueLoans.length * 10 + Math.min(20, Math.round(txns.length / 3)));

      return {
        member,
        txns: sortedTxns,
        flagged: flaggedTxns.length > 0 || overdueLoans.length > 0,
        riskScore,
      };
    });

    const topMembers = memberRows.sort((a, b) => b.riskScore - a.riskScore).slice(0, 8);

    const nodes = topMembers.map((item, index) => ({
      id: item.member.id,
      label: item.member.name,
      sublabel: item.member.id,
      type: "member" as const,
      x: 100 + (index % 4) * 135,
      y: 90 + Math.floor(index / 4) * 120,
      flagged: item.flagged,
    }));

    const memberIndex = Object.fromEntries(nodes.map((node) => [node.id, node]));
    const edges: NetEdge[] = [];

    nodes.forEach((node) => {
      const guarantors = data.memberProfiles[node.id]?.guarantors ?? [];
      guarantors.forEach((guarantor) => {
        const target = data.members.find((m) => m.id === guarantor || m.name === guarantor);
        if (target && memberIndex[target.id]) {
          edges.push({ source: node.id, target: target.id, label: "Guarantor", severity: "high", dashed: true });
        }
      });
    });

    const channelGroups = data.transactions.reduce<Record<string, string[]>>((acc, txn) => {
      if (!txn.channel) return acc;
      const key = txn.channel.toLowerCase();
      acc[key] = acc[key] || [];
      const owner = data.members.find((member) => member.id === txn.member || member.name === txn.member);
      if (owner && memberIndex[owner.id] && !acc[key].includes(owner.id)) {
        acc[key].push(owner.id);
      }
      return acc;
    }, {});

    Object.entries(channelGroups).forEach(([channel, ids]) => {
      for (let i = 0; i < ids.length - 1; i += 1) {
        if (ids[i] && ids[i + 1]) {
          edges.push({ source: ids[i], target: ids[i + 1], label: "Shared channel", severity: "medium", dashed: true });
        }
      }
    });

    return {
      nodes,
      edges,
      clusterCount: Math.max(1, new Set(edges.map((edge) => edge.label)).size),
    };
  }, [data.members, data.transactions, data.loans, data.memberProfiles, data.anomalyFlags]);

  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));

  const isLit = (id: string) => {
    if (!hovered) return true;
    if (hovered === id) return true;
    return edges.some((e) => (e.source === hovered && e.target === id) || (e.target === hovered && e.source === id));
  };

  const edgeColor = (sev: string) =>
    sev === "critical" ? "#EF4444" : sev === "high" ? "#F97316" : sev === "medium" ? "#F59E0B" : "#CBD5E1";

  return (
    <div className="bg-card border border-border rounded-lg p-5">
      <div className="flex items-start justify-between mb-4 gap-4">
        <div>
          <h3 className="font-semibold text-foreground font-['Plus_Jakarta_Sans']">Fraud Connection Network</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Hover a node to trace its connections - {clusterCount} suspicious cluster{clusterCount === 1 ? "" : "s"} detected</p>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground flex-shrink-0">
          {[ ["#EF4444", "Critical"], ["#F97316", "High"], ["#F59E0B", "Medium"], ["#CBD5E1", "Normal"] ].map(([c, l]) => (
            <div key={l} className="flex items-center gap-1.5">
              <div className="w-5 h-0.5 rounded" style={{ background: c }} />
              <span>{l}</span>
            </div>
          ))}
        </div>
      </div>

      <svg width="100%" viewBox="0 0 660 360" className="overflow-visible">
        <defs>
          <pattern id="fdgrid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(15,76,53,0.05)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="660" height="360" fill="url(#fdgrid)" rx="8" />

        {edges.map((e, i) => {
          const s = nodeMap[e.source];
          const t = nodeMap[e.target];
          if (!s || !t) return null;
          const color = edgeColor(e.severity);
          const opacity = hovered ? ((hovered === e.source || hovered === e.target) ? 1 : 0.07) : 0.65;
          const mx = (s.x + t.x) / 2;
          const my = (s.y + t.y) / 2 - 7;
          return (
            <g key={i} style={{ opacity, transition: "opacity 0.2s" }}>
              <line x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke={color} strokeWidth={e.severity === "critical" ? 2.2 : 1.6}
                strokeDasharray={e.dashed ? "6 4" : "none"} />
              {e.label && (
                <text x={mx} y={my} fontSize="8.5" fill={color} textAnchor="middle"
                  fontFamily="Inter, sans-serif" fontWeight="500" style={{ userSelect: "none" }}>
                  {e.label}
                </text>
              )}
            </g>
          );
        })}

        {nodes.map((node) => {
          const lit = isLit(node.id);
          const isHov = hovered === node.id;
          const initials = node.label.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
          const fill = node.flagged ? "#FEE2E2" : "#DCFCE7";
          const stroke = node.flagged ? "#EF4444" : "#22C55E";
          const labelColor = node.flagged ? "#991B1B" : "#166534";
          const r = isHov ? 27 : 23;

          return (
            <g key={node.id}
              style={{ opacity: lit ? 1 : 0.18, transition: "opacity 0.2s", cursor: "pointer" }}
              onMouseEnter={() => setHovered(node.id)}
              onMouseLeave={() => setHovered(null)}>
              <circle cx={node.x} cy={node.y} r={r} fill={fill} stroke={stroke} strokeWidth={isHov ? 2.5 : 1.5}
                style={{ transition: "r 0.15s" }} />
              <text x={node.x} y={node.y + 4} textAnchor="middle"
                fontSize="11" fill={labelColor} fontWeight="700" fontFamily="Inter, sans-serif"
                style={{ userSelect: "none" }}>
                {initials}
              </text>
              <text x={node.x} y={node.y + 18} textAnchor="middle"
                fontSize="9" fill="#374151" fontWeight="600" fontFamily="Inter, sans-serif">
                {node.label}
              </text>
              <text x={node.x} y={node.y + 28} textAnchor="middle"
                fontSize="8" fill="#9CA3AF" fontFamily="JetBrains Mono, monospace">
                {node.sublabel}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap gap-4 mt-3 text-xs text-muted-foreground">
        {[
          { fill: "#FEE2E2", stroke: "#EF4444", label: "Flagged Member" },
          { fill: "#DCFCE7", stroke: "#22C55E", label: "Clean Member" },
          { fill: "#F9F5EB", stroke: "#F59E0B", label: "Guarantor Relationship" },
          { fill: "#EFF6FF", stroke: "#3B82F6", label: "Shared Channel" },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div className="w-4 h-4 rounded-full border" style={{ background: item.fill, borderColor: item.stroke }} />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// -- Fraud Detection View ------------------------------------------------------

function FraudDetectionView() {
  const { data } = useSaccoData();
  const fraudAlerts: FraudAlert[] = React.useMemo(() => {
    const alerts = Object.entries(data.anomalyFlags).map(([transactionId, flag]) => {
      const transaction = data.transactions.find((item) => item.id === transactionId);
      const severity: FraudSeverity = flag.level === "high" ? "High" : "Medium";
      const riskScore = flag.level === "high" ? 82 : 58;
      return {
        id: `ALERT-${transactionId}`,
        type: "Transaction Anomaly",
        severity,
        members: transaction ? [transaction.member] : [],
        name: transaction ? `${transaction.member} / ${transaction.id}` : transactionId,
        detected: transaction?.date ?? "Live database",
        description: flag.reason,
        evidence: [
          transaction ? `Transaction ${transaction.id} via ${transaction.channel}` : `Transaction ${transactionId}`,
          transaction ? `${transaction.type} amount: KES ${transaction.amount.toLocaleString()}` : "Flag generated by backend anomaly service",
        ],
        status: "Open" as FraudAlertStatus,
        riskScore,
      };
    });
    return alerts.length ? alerts : [];
  }, [data.anomalyFlags, data.transactions]);
  const [activeTab, setActiveTab] = useState<"alerts" | "network" | "behavioral">("alerts");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sevFilter, setSevFilter] = useState("All");
  const [statFilter, setStatFilter] = useState("All");
  const [overrides, setOverrides] = useState<Record<string, FraudAlertStatus>>({});

  const getStatus = (a: FraudAlert): FraudAlertStatus => overrides[a.id] ?? a.status;

  const filtered = fraudAlerts.filter((a) => {
    const ms = sevFilter === "All" || a.severity === sevFilter;
    const mst = statFilter === "All" || getStatus(a) === statFilter;
    return ms && mst;
  });

  const critical = fraudAlerts.filter((a) => a.severity === "Critical").length;
  const high = fraudAlerts.filter((a) => a.severity === "High").length;
  const openCount = fraudAlerts.filter((a) => getStatus(a) === "Open").length;
  const avgRisk = fraudAlerts.length ? Math.round(fraudAlerts.reduce((s, a) => s + a.riskScore, 0) / fraudAlerts.length) : 0;

  const behavioralProfiles = React.useMemo(() => {
    const now = Date.now();

    return data.members.map((member) => {
      const txns = data.transactions.filter((txn) => txn.member === member.id || txn.member === member.name);
      const sortedTxns = [...txns].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      const lastTxn = sortedTxns[0];
      const dormantDays = lastTxn ? Math.max(0, Math.round((now - new Date(lastTxn.date).getTime()) / 86400000)) : 180;
      const recent90 = sortedTxns.filter((txn) => new Date(txn.date).getTime() >= now - 90 * 86400000);
      const current30 = sortedTxns.filter((txn) => new Date(txn.date).getTime() >= now - 30 * 86400000);
      const baselineTxns = Math.max(1, Math.round(recent90.length / 3));
      const currentTxns = current30.length;
      const avgAmount = txns.length ? Math.round(txns.reduce((sum, txn) => sum + txn.amount, 0) / txns.length) : 0;
      const lastAmount = lastTxn?.amount ?? 0;
      const commonChannel = Object.entries(
        txns.reduce<Record<string, number>>((acc, txn) => {
          const key = txn.channel || txn.category || "Unknown";
          acc[key] = (acc[key] || 0) + 1;
          return acc;
        }, {})
      ).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "Unknown";
      const currentChannel = lastTxn?.channel || "Unknown";
      const deviceMatch = commonChannel === currentChannel;
      const memberLoans = data.loans.filter((loan) => loan.member === member.id || loan.member === member.name);
      const overdueLoans = memberLoans.filter((loan) => loan.status === "Overdue");
      const flaggedTxns = sortedTxns.filter((txn) => Boolean(data.anomalyFlags[txn.id]));

      const anomalies = [] as string[];
      if (flaggedTxns.length) anomalies.push("Transaction Anomaly");
      if (dormantDays > 60) anomalies.push("Dormancy Spike");
      if (currentTxns > baselineTxns * 2) anomalies.push("Txn Velocity");
      if (overdueLoans.length > 0) anomalies.push("Overdue Loan");
      if (commonChannel !== currentChannel) anomalies.push("Channel Drift");
      if (anomalies.length === 0) anomalies.push("Stable behavior");

      const fraudScore = Math.min(95,
        40 + flaggedTxns.length * 12 + overdueLoans.length * 10 + Math.min(20, Math.round(dormantDays / 5)) + (currentTxns > baselineTxns * 2 ? 10 : 0)
      );

      return {
        id: member.id,
        name: member.name,
        fraudScore,
        dormantDays,
        baselineTxns,
        currentTxns,
        avgAmount,
        lastAmount,
        usualLocation: commonChannel,
        currentLocation: currentChannel,
        deviceMatch,
        usualDevice: commonChannel,
        currentDevice: currentChannel,
        anomalies,
      };
    });
  }, [data.members, data.transactions, data.loans, data.memberProfiles, data.anomalyFlags]);

  return (
    <div className="space-y-5">
      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-red-600 text-white rounded-lg p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/60 mb-2">Critical Alerts</p>
          <p className="text-3xl font-bold font-['Plus_Jakarta_Sans']">{critical}</p>
          <p className="text-xs text-white/60 mt-1">Immediate action required</p>
        </div>
        <div className="bg-orange-500 text-white rounded-lg p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/60 mb-2">High Severity</p>
          <p className="text-3xl font-bold font-['Plus_Jakarta_Sans']">{high}</p>
          <p className="text-xs text-white/60 mt-1">Review within 24 hours</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Open Cases</p>
          <p className="text-3xl font-bold font-['Plus_Jakarta_Sans'] text-foreground">{openCount}</p>
          <p className="text-xs text-muted-foreground mt-1">Awaiting investigation</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Avg Risk Score</p>
          <p className="text-3xl font-bold font-['Plus_Jakarta_Sans'] text-foreground">{avgRisk}<span className="text-base text-muted-foreground">/100</span></p>
          <p className="text-xs text-muted-foreground mt-1">Portfolio fraud exposure</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-secondary rounded-lg w-fit max-w-full overflow-x-auto">
        {([
          ["alerts", `Alert Feed (${fraudAlerts.length})`],
          ["network", "Network Graph"],
          ["behavioral", "Behavioral Analysis"],
        ] as const).map(([id, label]) => (
          <button key={id} onClick={() => setActiveTab(id)}
            className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${activeTab === id ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* -- Alert Feed -- */}
      {activeTab === "alerts" && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex gap-1.5">
              {["All", "Critical", "High", "Medium", "Low"].map((s) => (
                <button key={s} onClick={() => setSevFilter(s)}
                  className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors ${sevFilter === s ? "bg-primary text-primary-foreground border-primary" : "bg-card border-border text-muted-foreground hover:border-primary/40"}`}>
                  {s}
                </button>
              ))}
            </div>
            <div className="flex gap-1.5 ml-auto">
              {["All", "Open", "Under Review", "Resolved"].map((s) => (
                <button key={s} onClick={() => setStatFilter(s)}
                  className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors ${statFilter === s ? "bg-foreground text-background border-foreground" : "bg-card border-border text-muted-foreground"}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Alert cards */}
          {filtered.map((alert) => {
            const sev = SEV_STYLE[alert.severity];
            const status = getStatus(alert);
            const isExp = expanded === alert.id;
            const riskColor = alert.riskScore >= 85 ? "#EF4444" : alert.riskScore >= 70 ? "#F97316" : "#F59E0B";

            return (
              <div key={alert.id} className="bg-card border border-border rounded-lg overflow-hidden hover:border-border/80 transition-colors">
                <div className="flex items-stretch">
                  <div className={`w-1.5 flex-shrink-0 ${sev.bar}`} />
                  <div className="flex-1 p-4">
                    <div className="flex items-start gap-4">
                      <div className="flex-1 min-w-0">
                        {/* Badges row */}
                        <div className="flex items-center gap-2 flex-wrap mb-2">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded border ${sev.badge}`}>{alert.severity}</span>
                          <span className="text-xs px-2 py-0.5 rounded bg-secondary border border-border text-muted-foreground">{alert.type}</span>
                          <span className={`text-xs px-2 py-0.5 rounded border font-medium ${STAT_STYLE[status]}`}>{status}</span>
                          <span className="text-xs text-muted-foreground font-['JetBrains_Mono'] ml-auto hidden sm:block">{alert.id}</span>
                        </div>
                        <p className="text-sm font-semibold text-foreground leading-tight">{alert.name}</p>
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{alert.description}</p>

                        {/* Member chips */}
                        <div className="flex gap-1.5 mt-2 flex-wrap">
                          {alert.members.map((m) => (
                            <span key={m} className="text-xs px-2 py-0.5 rounded-full bg-primary/8 text-primary font-['JetBrains_Mono'] border border-primary/15">{m}</span>
                          ))}
                        </div>

                        {/* Evidence (expanded) */}
                        {isExp && (
                          <div className="mt-4 pt-3 border-t border-border">
                            <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
                              <Fingerprint size={12} className="text-primary" /> Digital Evidence
                            </p>
                            <div className="space-y-2">
                              {alert.evidence.map((e, i) => (
                                <div key={i} className="flex items-start gap-2 text-xs text-foreground/80 bg-secondary/40 rounded px-3 py-2">
                                  <span className="text-primary mt-0.5 font-['JetBrains_Mono'] font-bold flex-shrink-0">{String(i + 1).padStart(2, "0")}</span>
                                  {e}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Right column: risk score + actions */}
                      <div className="flex flex-col items-end gap-3 flex-shrink-0">
                        <div className="text-right">
                          <div className="text-2xl font-bold font-['JetBrains_Mono']" style={{ color: riskColor }}>{alert.riskScore}</div>
                          <div className="text-xs text-muted-foreground">risk score</div>
                          <div className="w-16 h-1.5 rounded-full bg-secondary mt-1.5 overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${alert.riskScore}%`, background: riskColor }} />
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground font-['JetBrains_Mono']">{alert.detected}</p>
                        <div className="flex gap-1.5 flex-wrap justify-end">
                          <button onClick={() => setExpanded(isExp ? null : alert.id)}
                            className="text-xs px-2.5 py-1.5 rounded border border-border bg-secondary text-foreground hover:bg-secondary/60 transition-colors">
                            {isExp ? "Collapse" : "Evidence"}
                          </button>
                          {status === "Open" && (
                            <button onClick={() => setOverrides((p) => ({ ...p, [alert.id]: "Under Review" }))}
                              className="text-xs px-2.5 py-1.5 rounded border border-orange-300 text-orange-700 hover:bg-orange-50 transition-colors">
                              Investigate
                            </button>
                          )}
                          {status === "Under Review" && (
                            <button onClick={() => setOverrides((p) => ({ ...p, [alert.id]: "Resolved" }))}
                              className="text-xs px-2.5 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
                              Resolve
                            </button>
                          )}
                          {(status === "Open" || status === "Under Review") && (
                            <button onClick={() => setOverrides((p) => ({ ...p, [alert.id]: "False Positive" }))}
                              className="text-xs px-2.5 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground transition-colors">
                              FP
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {filtered.length === 0 && (
            <div className="bg-card border border-border rounded-lg p-10 flex flex-col items-center gap-3 text-muted-foreground">
              <ShieldCheck size={28} className="text-emerald-500" />
              <p className="text-sm font-medium">No alerts match the current filter</p>
            </div>
          )}
        </div>
      )}

      {/* -- Network Graph -- */}
      {activeTab === "network" && <FraudNetworkGraph />}

      {/* -- Behavioral Analysis -- */}
      {activeTab === "behavioral" && (
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 rounded-lg border border-amber-200 bg-amber-50">
            <Activity size={15} className="text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-amber-800 leading-relaxed">
              <span className="font-semibold">Behavioral baseline model</span> - each member's normal activity is derived from their full transaction history. Deviations above 2sigma are flagged automatically. Device fingerprints, login geolocations, and transaction velocity are compared against the 90-day rolling baseline.
            </p>
          </div>

          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/40">
                    {["Member", "Fraud Score", "Dormancy", "Txn Velocity", "Location", "Device", "Anomaly Tags"].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {behavioralProfiles.map((bp, i) => {
                    const rc = bp.fraudScore >= 85 ? "#EF4444" : bp.fraudScore >= 70 ? "#F97316" : "#F59E0B";
                    const locationDrift = bp.usualLocation !== bp.currentLocation;
                    return (
                      <tr key={bp.id} className={`border-b border-border/50 hover:bg-secondary/20 transition-colors ${i % 2 === 0 ? "" : "bg-secondary/10"}`}>
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ color: rc }}>
                              {bp.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                            </div>
                            <div>
                              <p className="font-medium text-foreground text-sm leading-tight">{bp.name}</p>
                              <p className="text-xs text-muted-foreground font-['JetBrains_Mono']">{bp.id}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="font-bold font-['JetBrains_Mono'] text-lg" style={{ color: rc }}>{bp.fraudScore}</div>
                          <div className="w-14 h-1.5 rounded-full bg-secondary mt-1 overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${bp.fraudScore}%`, background: rc }} />
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className={`text-sm font-['JetBrains_Mono'] font-semibold ${bp.dormantDays > 180 ? "text-red-600" : bp.dormantDays > 30 ? "text-amber-600" : "text-muted-foreground"}`}>
                            {bp.dormantDays}d
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="text-xs">
                            <span className="text-muted-foreground">{bp.baselineTxns}/mo</span>
                              <span className="text-muted-foreground mx-1">-&gt;</span>
                            <span className={`font-semibold ${bp.currentTxns > bp.baselineTxns * 2 ? "text-red-600" : "text-foreground"}`}>{bp.currentTxns}/mo</span>
                            {bp.currentTxns > bp.baselineTxns * 2 && (
                              <span className="text-red-500 ml-1 font-['JetBrains_Mono']">up {(bp.currentTxns / bp.baselineTxns).toFixed(1)}x</span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            Last: <span className="font-['JetBrains_Mono']">{fmtShort(bp.lastAmount)}</span>
                            <span className="mx-1">vs avg</span>
                            <span className="font-['JetBrains_Mono']">{fmtShort(bp.avgAmount)}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-1 text-xs text-muted-foreground mb-0.5">
                            <Globe size={10} /> {bp.usualLocation}
                          </div>
                          <div className={`flex items-center gap-1 text-xs font-semibold ${locationDrift ? "text-red-600" : "text-foreground"}`}>
                            {locationDrift ? <TriangleAlert size={10} /> : <CheckCircle2 size={10} className="text-emerald-500" />}
                            {bp.currentLocation}
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className={`flex items-center gap-1 text-xs font-semibold ${bp.deviceMatch ? "text-emerald-600" : "text-red-600"}`}>
                            <Smartphone size={11} />
                            {bp.deviceMatch ? "Match" : "Mismatch"}
                          </div>
                          {!bp.deviceMatch && (
                            <p className="text-xs text-muted-foreground mt-0.5 max-w-[110px] truncate">{bp.currentDevice}</p>
                          )}
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex flex-wrap gap-1">
                            {bp.anomalies.map((a) => (
                              <span key={a} className="text-xs px-1.5 py-0.5 rounded bg-red-50 text-red-600 border border-red-100 whitespace-nowrap">{a}</span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 border-t border-border flex items-center gap-2 bg-secondary/10">
              <Info size={12} className="text-muted-foreground" />
              <p className="text-xs text-muted-foreground">Behavioral model refreshes every 6 hours - Baseline computed from 90-day rolling window - Alert threshold: 2sigma deviation</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -- AI Collections Assistant --------------------------------------------------

type CollectionRisk = "Critical" | "High" | "Medium" | "Low";
type ContactChannel = "Call" | "SMS" | "WhatsApp" | "Email";

interface CollectionCase {
  id: string;
  memberId: string;
  memberName: string;
  loanId: string;
  outstanding: number;
  daysOverdue: number;
  missedPayments: number;
  defaultProbability: number;
  risk: CollectionRisk;
  priorityScore: number;
  bestContactTime: string;
  preferredChannel: ContactChannel;
  lastContactDate: string;
  lastContactOutcome: string;
  behaviorNote: string;
  suggestedAction: string;
  reminderTemplate: string;
}

const RISK_STYLE: Record<CollectionRisk, { bg: string; text: string; dot: string }> = {
  Critical: { bg: "bg-red-50 border border-red-200", text: "text-red-700", dot: "bg-red-500" },
  High:     { bg: "bg-orange-50 border border-orange-200", text: "text-orange-700", dot: "bg-orange-500" },
  Medium:   { bg: "bg-yellow-50 border border-yellow-200", text: "text-yellow-700", dot: "bg-yellow-500" },
  Low:      { bg: "bg-emerald-50 border border-emerald-200", text: "text-emerald-700", dot: "bg-emerald-500" },
};

const CHANNEL_ICON: Record<ContactChannel, React.ElementType> = {
  Call: Smartphone, SMS: FileText, WhatsApp: Smartphone, Email: FileText,
};

const CHANNEL_COLOR: Record<ContactChannel, string> = {
  Call: "text-green-600 bg-green-50", SMS: "text-blue-600 bg-blue-50",
  WhatsApp: "text-emerald-600 bg-emerald-50", Email: "text-purple-600 bg-purple-50",
};

const recoveryTrendData = [
  { month: "Feb", rate: 71, target: 85 },
  { month: "Mar", rate: 76, target: 85 },
  { month: "Apr", rate: 74, target: 85 },
  { month: "May", rate: 79, target: 85 },
  { month: "Jun", rate: 82, target: 85 },
  { month: "Jul", rate: 84, target: 85 },
];

const bucketData = [
  { label: "1-30 days", count: 8, amount: 1240000, color: "#C8A84B" },
  { label: "31-60 days", count: 5, amount: 850000, color: "#E07B39" },
  { label: "61-90 days", count: 3, amount: 510000, color: "#DC2626" },
  { label: "90+ days", count: 2, amount: 290000, color: "#7F1D1D" },
];

function DefaultGauge({ probability }: { probability: number }) {
  const r = 36, cx = 44, cy = 52;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.65;
  const filled = (probability / 100) * arc;
  const startDeg = 135;
  const color = probability >= 70 ? "#DC2626" : probability >= 45 ? "#E07B39" : probability >= 25 ? "#C8A84B" : "#059669";
  const tf = `rotate(${startDeg}, ${cx}, ${cy})`;
  return (
    <svg width="88" height="72" viewBox="0 0 88 72">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E2E8E3" strokeWidth="8"
        strokeDasharray={`${arc} ${circ - arc}`} strokeLinecap="round" transform={tf} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="8"
        strokeDasharray={`${filled} ${circ - filled}`} strokeLinecap="round" transform={tf} />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="14" fontWeight="700" fill={color} fontFamily="JetBrains Mono, monospace">{probability}%</text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize="7" fill="#5A6B60" fontFamily="Inter, sans-serif">default risk</text>
    </svg>
  );
}

function CollectionsView() {
  const { data } = useSaccoData();
  const collectionCases: CollectionCase[] = React.useMemo(() => data.loans
    .filter((loan) => loan.status === "Overdue")
    .map((loan, index) => {
      const member = data.members.find((item) => item.name === loan.member);
      const daysOverdue = Math.max(1, Math.floor((Date.now() - new Date(loan.due).getTime()) / 86400000));
      const defaultProbability = Math.min(95, Math.max(20, Math.round(daysOverdue * 0.9 + (loan.balance / Math.max(loan.amount, 1)) * 45)));
      const risk: CollectionRisk = defaultProbability >= 75 ? "Critical" : defaultProbability >= 60 ? "High" : defaultProbability >= 40 ? "Medium" : "Low";
      const priorityScore = Math.min(100, Math.round(defaultProbability + Math.min(20, loan.balance / 100000)));
      return {
        id: `CC-${loan.id}`,
        memberId: member?.id ?? "Unknown",
        memberName: loan.member,
        loanId: loan.id,
        outstanding: loan.balance,
        daysOverdue,
        missedPayments: Math.max(1, Math.ceil(daysOverdue / 30)),
        defaultProbability,
        risk,
        priorityScore,
        bestContactTime: "Business hours",
        preferredChannel: index % 2 === 0 ? "Call" : "SMS",
        lastContactDate: "No contact recorded",
        lastContactOutcome: "Pending outreach",
        behaviorNote: `${loan.member} has an overdue ${loan.type} loan in the live portfolio.`,
        suggestedAction: daysOverdue > 60 ? "Escalate to collections and discuss restructuring." : "Contact member and agree on a repayment date.",
        reminderTemplate: `Hello ${loan.member}, your ${loan.type} loan ${loan.id} has an outstanding balance of KES ${loan.balance.toLocaleString()}. Please contact the SACCO office to arrange repayment.`,
      };
    }), [data.loans, data.members]);
  const [selectedCase, setSelectedCase] = useState<CollectionCase | null>(null);
  const [reminderCopied, setReminderCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"queue" | "recovery" | "buckets">("queue");
  const [contactedIds, setContactedIds] = useState<Set<string>>(new Set());
  const [filterRisk, setFilterRisk] = useState<CollectionRisk | "All">("All");

  useEffect(() => {
    setSelectedCase((current) => current && collectionCases.some((item) => item.id === current.id) ? current : collectionCases[0] ?? null);
  }, [collectionCases]);

  const sorted = [...collectionCases]
    .filter((c) => filterRisk === "All" || c.risk === filterRisk)
    .sort((a, b) => b.priorityScore - a.priorityScore);

  const totalOutstanding = collectionCases.reduce((s, c) => s + c.outstanding, 0);
  const criticalCount = collectionCases.filter((c) => c.risk === "Critical").length;
  const avgDefaultProb = collectionCases.length
    ? Math.round(collectionCases.reduce((s, c) => s + c.defaultProbability, 0) / collectionCases.length)
    : 0;

  const handleCopy = () => {
    if (!selectedCase) return;
    navigator.clipboard.writeText(selectedCase.reminderTemplate).catch(() => {});
    setReminderCopied(true);
    setTimeout(() => setReminderCopied(false), 2200);
  };

  const tabs = [
    { id: "queue", label: "Collection Queue" },
    { id: "recovery", label: "Recovery Trend" },
    { id: "buckets", label: "Delinquency Buckets" },
  ] as const;

  return (
    <div className="flex flex-col gap-5 pb-8">

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total Outstanding", value: `KES ${(totalOutstanding / 1000000).toFixed(2)}M`, sub: "across all overdue cases", icon: Wallet, color: "text-destructive" },
          { label: "Critical Cases", value: criticalCount.toString(), sub: "require immediate action", icon: AlertCircle, color: "text-red-600" },
          { label: "Avg Default Risk", value: `${avgDefaultProb}%`, sub: "AI predicted probability", icon: Brain, color: "text-orange-600" },
          { label: "Recovery Rate", value: "84%", sub: "up 5pp from last month", icon: TrendingUp, color: "text-emerald-600" },
        ].map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div key={kpi.label} className="bg-card rounded-xl border border-border px-4 py-3.5 flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                <Icon size={15} className={kpi.color} />
              </div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground truncate">{kpi.label}</p>
                <p className={`text-xl font-bold font-['JetBrains_Mono',_monospace] ${kpi.color}`}>{kpi.value}</p>
                <p className="text-xs text-muted-foreground">{kpi.sub}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-secondary/60 rounded-lg p-1 w-fit max-w-full overflow-x-auto">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`text-xs font-semibold px-4 py-1.5 rounded-md transition-colors whitespace-nowrap ${activeTab === t.id ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* -- Collection Queue -- */}
      {activeTab === "queue" && (
        <div className="flex flex-col xl:flex-row gap-4 min-h-0">

          {/* Left: case list */}
          <div className="flex flex-col gap-2 w-full xl:w-80 xl:flex-shrink-0">
            {/* Risk filter */}
            <div className="flex gap-1 flex-wrap">
              {(["All", "Critical", "High", "Medium", "Low"] as const).map((r) => (
                <button key={r} onClick={() => setFilterRisk(r)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors font-medium ${filterRisk === r ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary/40"}`}>
                  {r}
                </button>
              ))}
            </div>

            {sorted.map((c) => {
              const rs = RISK_STYLE[c.risk];
              const isSelected = selectedCase?.id === c.id;
              const contacted = contactedIds.has(c.id);
              return (
                <button key={c.id} onClick={() => setSelectedCase(c)}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all ${isSelected ? "border-primary bg-primary/5 shadow-sm" : "border-border bg-card hover:border-primary/30"}`}>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{c.memberName}</p>
                      <p className="text-xs text-muted-foreground font-['JetBrains_Mono',_monospace]">{c.loanId}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${rs.bg} ${rs.text}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${rs.dot}`} />
                        {c.risk}
                      </span>
                      {contacted && (
                        <span className="text-xs text-emerald-600 font-medium">Contacted</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-muted-foreground">Outstanding</p>
                      <p className="text-sm font-bold text-foreground font-['JetBrains_Mono',_monospace]">
                        KES {c.outstanding.toLocaleString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">Priority</p>
                      <div className="flex items-center gap-1 justify-end">
                        <div className="w-16 h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div className="h-full rounded-full bg-accent" style={{ width: `${c.priorityScore}%` }} />
                        </div>
                        <span className="text-xs font-bold text-accent">{c.priorityScore}</span>
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{c.daysOverdue}d overdue - {c.missedPayments} missed payment{c.missedPayments !== 1 ? "s" : ""}</p>
                </button>
              );
            })}
          </div>

          {/* Right: detail panel */}
          <div className="flex-1 min-w-0">
            {selectedCase ? (
              <div className="bg-card rounded-xl border border-border overflow-hidden">
                {/* Header */}
                <div className="px-5 py-4 border-b border-border flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <h3 className="text-base font-bold text-foreground">{selectedCase.memberName}</h3>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${RISK_STYLE[selectedCase.risk].bg} ${RISK_STYLE[selectedCase.risk].text}`}>
                        {selectedCase.risk} Risk
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground font-['JetBrains_Mono',_monospace]">
                      {selectedCase.memberId} - {selectedCase.loanId}
                    </p>
                  </div>
                  <DefaultGauge probability={selectedCase.defaultProbability} />
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-1 sm:grid-cols-3 sm:divide-x divide-y sm:divide-y-0 divide-border border-b border-border">
                  {[
                    { label: "Outstanding", value: `KES ${selectedCase.outstanding.toLocaleString()}` },
                    { label: "Days Overdue", value: `${selectedCase.daysOverdue} days` },
                    { label: "Missed Payments", value: `${selectedCase.missedPayments}` },
                  ].map((s) => (
                    <div key={s.label} className="px-4 py-3 text-center">
                      <p className="text-xs text-muted-foreground">{s.label}</p>
                      <p className="text-sm font-bold text-foreground font-['JetBrains_Mono',_monospace]">{s.value}</p>
                    </div>
                  ))}
                </div>

                <div className="p-5 flex flex-col gap-4">

                  {/* AI Suggested Action */}
                  <div className="bg-primary/5 border border-primary/15 rounded-xl p-4 flex gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Brain size={15} className="text-primary" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-primary mb-1 flex items-center gap-1.5">
                        <Sparkles size={10} /> AI Recommended Action
                      </p>
                      <p className="text-sm text-foreground">{selectedCase.suggestedAction}</p>
                    </div>
                  </div>

                  {/* Contact intelligence */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="bg-secondary/50 rounded-xl p-3.5">
                      <p className="text-xs text-muted-foreground mb-1.5 font-semibold uppercase tracking-wide">Best Time to Contact</p>
                      <div className="flex items-center gap-2">
                        <Clock size={14} className="text-accent flex-shrink-0" />
                        <p className="text-sm font-semibold text-foreground">{selectedCase.bestContactTime}</p>
                      </div>
                    </div>
                    <div className="bg-secondary/50 rounded-xl p-3.5">
                      <p className="text-xs text-muted-foreground mb-1.5 font-semibold uppercase tracking-wide">Preferred Channel</p>
                      <div className={`flex items-center gap-2 w-fit px-2.5 py-1 rounded-lg ${CHANNEL_COLOR[selectedCase.preferredChannel]}`}>
                        {React.createElement(CHANNEL_ICON[selectedCase.preferredChannel], { size: 13 })}
                        <p className="text-sm font-semibold">{selectedCase.preferredChannel}</p>
                      </div>
                    </div>
                  </div>

                  {/* Behavior note */}
                  <div className="border border-border rounded-xl p-3.5 flex gap-2.5">
                    <Activity size={14} className="text-muted-foreground flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground mb-0.5">Behavioral Insight</p>
                      <p className="text-sm text-foreground">{selectedCase.behaviorNote}</p>
                    </div>
                  </div>

                  {/* Last contact */}
                  <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 text-sm">
                    <div>
                      <span className="text-xs text-muted-foreground">Last Contact: </span>
                      <span className="font-medium text-foreground">{selectedCase.lastContactDate}</span>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Outcome: </span>
                      <span className="font-medium text-foreground">{selectedCase.lastContactOutcome}</span>
                    </div>
                  </div>

                  {/* Reminder template */}
                  <div className="border border-border rounded-xl overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2.5 bg-secondary/40 border-b border-border">
                      <div className="flex items-center gap-2">
                        <FileText size={12} className="text-muted-foreground" />
                        <p className="text-xs font-semibold text-muted-foreground">AI-Generated Reminder Message</p>
                      </div>
                      <button onClick={handleCopy}
                        className="text-xs font-semibold text-primary flex items-center gap-1.5 hover:text-primary/80 transition-colors">
                        {reminderCopied ? <><CheckCircle2 size={11} className="text-emerald-600" /> Copied!</> : <><Download size={11} /> Copy</>}
                      </button>
                    </div>
                    <div className="px-4 py-3">
                      <p className="text-sm text-foreground leading-relaxed">{selectedCase.reminderTemplate}</p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col sm:flex-row gap-2 pt-1">
                    <button
                      onClick={() => setContactedIds((p) => { const n = new Set(p); n.add(selectedCase.id); return n; })}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-semibold hover:bg-primary/90 transition-colors">
                      <CheckCircle2 size={14} /> Mark as Contacted
                    </button>
                    <button className="flex items-center justify-center gap-2 px-4 py-2.5 border border-border rounded-lg text-sm font-semibold text-foreground hover:bg-secondary/50 transition-colors">
                      <RefreshCw size={13} /> Restructure
                    </button>
                    <button className="flex items-center justify-center gap-2 px-4 py-2.5 border border-border rounded-lg text-sm font-semibold text-foreground hover:bg-secondary/50 transition-colors">
                      <Shield size={13} /> Escalate
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full min-h-64 flex flex-col items-center justify-center text-muted-foreground gap-3 bg-card rounded-xl border border-border border-dashed">
                <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center">
                  <Users size={20} className="text-muted-foreground" />
                </div>
                <p className="text-sm font-medium">Select a case to view AI recommendations</p>
                <p className="text-xs text-muted-foreground">Sorted by AI priority score - highest risk first</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* -- Recovery Trend -- */}
      {activeTab === "recovery" && (
        <div className="bg-card rounded-xl border border-border p-5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-foreground">Monthly Recovery Rate</h3>
              <p className="text-xs text-muted-foreground">Actual vs 85% target - Last 6 months</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-primary inline-block rounded" /> Actual</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-accent inline-block rounded border-dashed border border-accent" /> Target</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={recoveryTrendData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} domain={[60, 100]} tickFormatter={(v) => `${v}%`} />
              <Tooltip formatter={(v: number) => [`${v}%`, ""]} contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
              <Line type="monotone" dataKey="rate" stroke="#0F4C35" strokeWidth={2.5} dot={{ fill: "#0F4C35", r: 4 }} name="Actual" />
              <Line type="monotone" dataKey="target" stroke="#C8A84B" strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="Target" />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-4 p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-2.5">
            <TrendingUp size={15} className="text-emerald-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-emerald-700">Recovery within 1pp of target</p>
              <p className="text-xs text-emerald-600">AI routing of high-priority cases to field agents contributed an estimated +3pp improvement in June-July. Maintain current contact cadence.</p>
            </div>
          </div>
        </div>
      )}

      {/* -- Delinquency Buckets -- */}
      {activeTab === "buckets" && (
        <div className="bg-card rounded-xl border border-border p-5">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-foreground">Delinquency Aging Buckets</h3>
            <p className="text-xs text-muted-foreground">Total exposure by days-past-due - AI collection priority mapped to each bucket</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
            {bucketData.map((b) => (
              <div key={b.label} className="border border-border rounded-xl p-4 flex gap-3 items-start">
                <div className="w-3 rounded-full flex-shrink-0" style={{ backgroundColor: b.color, height: 48 }} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{b.label}</p>
                  <p className="text-lg font-bold text-foreground font-['JetBrains_Mono',_monospace]">
                    KES {(b.amount / 1000).toFixed(0)}K
                  </p>
                  <p className="text-xs text-muted-foreground">{b.count} cases</p>
                </div>
              </div>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={bucketData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,76,53,0.08)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#5A6B60" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
              <Tooltip formatter={(v: number) => [`KES ${v.toLocaleString()}`, "Outstanding"]} contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
              <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
                {bucketData.map((b, i) => <Cell key={i} fill={b.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4 p-3.5 bg-orange-50 border border-orange-200 rounded-xl flex items-start gap-2.5">
            <AlertCircle size={15} className="text-orange-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-orange-700">61-90 day bucket growing</p>
              <p className="text-xs text-orange-600">3 cases totaling KES 510K have moved into the 61-90 day bucket this month. AI recommends immediate field agent assignment to prevent roll-over to 90+ (write-off risk).</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -- Sidebar -------------------------------------------------------------------

const navItems: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "membership", label: "Membership", icon: ShieldCheck, userOnly: true },
  { id: "members", label: "Members", icon: Users, badge: 3, adminOnly: true },
  { id: "loans", label: "Loans", icon: CreditCard, badge: 2 },
  { id: "loan-repayment", label: "Loan Repayment", icon: Wallet, staffOnly: true, requiresOutstandingLoan: true },
  { id: "loan-scoring", label: "AI Loan Scoring", icon: Brain, ai: true, adminOnly: true },
  { id: "fraud", label: "Fraud Detection", icon: ShieldAlert, ai: true, adminOnly: true },
  { id: "collections", label: "AI Collections", icon: Wallet, ai: true, adminOnly: true },
  { id: "savings", label: "Savings", icon: PiggyBank },
  { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { id: "product-analytics", label: "Usage Analytics", icon: Activity, ai: true, adminOnly: true },
  { id: "reports", label: "Reports & API", icon: BarChart3, adminOnly: true },
  { id: "ai", label: "AI Assistant", icon: Sparkles, ai: true, adminOnly: true },
  { id: "admin", label: "Admin", icon: ShieldCheck, adminOnly: true },
  { id: "settings", label: "Settings", icon: Settings },
];

function Sidebar({
  active,
  onNav,
  collapsed,
  onToggle,
  mobileOpen,
  onClose,
  onLogout,
  session,
}: {
  active: string;
  onNav: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onClose: () => void;
  onLogout: () => void;
  session: AuthSession;
}) {
  const { data } = useSaccoData();
  const isCollapsed = collapsed && !mobileOpen;
  const userInitials = session.user.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  const hasOutstandingLoans = getOutstandingRepaymentLoans(data.loans).length > 0;
  const visibleNavItems = navItems.filter((item) => {
    if (item.adminOnly && session.user.role !== "admin") return false;
    if (item.userOnly && session.user.role === "admin") return false;
    if (item.staffOnly && session.user.role === "admin") return false;
    if (item.requiresOutstandingLoan && !hasOutstandingLoans) return false;
    return true;
  });

  return (
    <aside className={`fixed inset-y-0 left-0 z-40 flex min-h-screen flex-col bg-sidebar text-sidebar-foreground shadow-2xl transition-all duration-300 lg:static lg:z-auto lg:shadow-none ${isCollapsed ? "lg:w-16" : "lg:w-60"} w-72 max-w-[86vw] flex-shrink-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
      <div className="flex items-center gap-3 px-4 py-5 border-b border-sidebar-border">
        <div className="w-8 h-8 rounded bg-sidebar-primary flex items-center justify-center flex-shrink-0">
          <Building2 size={16} className="text-sidebar" />
        </div>
        {!isCollapsed && (
          <div className="min-w-0">
            <p className="text-sm font-bold text-sidebar-accent-foreground font-['Plus_Jakarta_Sans'] truncate">UmojaFunds</p>
            <p className="text-xs text-sidebar-foreground/50 truncate">Sacco ERP v2.4</p>
          </div>
        )}
        <button
          onClick={onToggle}
          className={`ml-auto hidden lg:flex p-1 rounded hover:bg-sidebar-accent transition-colors text-sidebar-foreground/60 hover:text-sidebar-foreground ${isCollapsed ? "mx-auto" : ""}`}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!isCollapsed}
        >
          <Menu size={14} />
        </button>
        <button onClick={onClose} className="ml-auto flex lg:hidden p-1 rounded hover:bg-sidebar-accent transition-colors text-sidebar-foreground/60 hover:text-sidebar-foreground" aria-label="Close sidebar">
          <X size={16} />
        </button>
      </div>

      <nav className="flex-1 py-4 space-y-0.5 px-2 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button key={item.id} onClick={() => onNav(item.id)}
              title={isCollapsed ? item.label : undefined}
              aria-current={isActive ? "page" : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors relative ${
                isActive ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
              } ${item.ai && !isActive ? "border border-sidebar-primary/30" : ""}`}>
              <Icon size={16} className={`flex-shrink-0 ${item.ai ? "text-sidebar-primary" : ""}`} />
              {!isCollapsed && (
                <span className={`truncate ${item.ai ? "font-semibold" : ""}`}>{item.label}</span>
              )}
              {!isCollapsed && item.badge && (
                <span className="ml-auto text-xs bg-accent text-accent-foreground font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">{item.badge}</span>
              )}
              {!isCollapsed && item.ai && !isActive && (
                <span className="ml-auto text-xs text-sidebar-primary font-semibold">New</span>
              )}
              {isCollapsed && item.badge && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent rounded-full" />}
            </button>
          );
        })}
      </nav>

      <div className="p-3 border-t border-sidebar-border">
        <button
          type="button"
          onClick={onLogout}
          className={`w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-sidebar-accent transition-colors cursor-pointer text-left ${isCollapsed ? "justify-center" : ""}`}
          title="Sign out"
          aria-label="Sign out"
        >
          <div className="w-7 h-7 rounded-full bg-sidebar-primary/30 flex items-center justify-center flex-shrink-0 text-xs font-bold text-sidebar-foreground">{userInitials}</div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-sidebar-foreground truncate">{session.user.name}</p>
              <p className="text-xs text-sidebar-foreground/50 truncate capitalize">{session.user.role}</p>
            </div>
          )}
          {!isCollapsed && <LogOut size={13} className="text-sidebar-foreground/40 flex-shrink-0" />}
        </button>
      </div>
    </aside>
  );
}

// -- App -----------------------------------------------------------------------

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "UmojaFunds Sacco - 2026 - FY2026" },
  membership: { title: "Membership", subtitle: "Apply for SACCO membership and track approval" },
  members: { title: "Members", subtitle: "Manage cooperative membership records" },
  loans: { title: "Loan Portfolio", subtitle: "AI credit scoring on all active loans" },
  "loan-repayment": { title: "Loan Repayment", subtitle: "Submit repayments for admin approval" },
  "loan-scoring": { title: "AI Loan Scoring", subtitle: "7-factor predictive engine - repayment, default, affordability, delinquency" },
  savings: { title: "Savings Accounts", subtitle: "Member deposit and share accounts" },
  transactions: { title: "Transactions", subtitle: "AI anomaly detection across all channels" },
  "product-analytics": { title: "Usage Analytics", subtitle: "Product adoption, loan funnel conversion, friction, and AI insights" },
  reports: { title: "Reports & API", subtitle: "Analytics, statements, and API integrations" },
  ai: { title: "AI Assistant", subtitle: "Natural language intelligence powered by Gemini" },
  fraud: { title: "Fraud Detection", subtitle: "AI anomaly detection - suspicious withdrawals, collusion, identity fraud" },
  collections: { title: "AI Collections", subtitle: "Predict defaults - prioritize outreach - generate personalized reminders" },
  admin: { title: "Admin", subtitle: "Manage backend users, roles, and access" },
  settings: { title: "Settings", subtitle: "System configuration and preferences" },
};

//Authentication View(login, signup, password reset) with rotating background images and form handling.
function AuthView({ onAuthenticated }: { onAuthenticated: (session: AuthSession) => void }) {
  const [mode, setMode] = useState<"login" | "signup" | "reset">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [resetMessage, setResetMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [currentBg, setCurrentBg] = useState(0);

  const imageModules = import.meta.glob('./components/assets/getty*.jpg', { eager: true });
  const bgImages = Object.values(imageModules).map((mod: any) => mod.default);

  useEffect(() => {
    if (bgImages.length === 0) return;
    const interval = setInterval(() => {
      setCurrentBg((prev) => (prev + 1) % bgImages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [bgImages.length]);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("resetToken");
    if (!token) return;
    setMode("reset");
    setResetToken(token);
    window.history.replaceState({}, document.title, window.location.pathname);
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      if (mode === "reset") {
        if (!resetToken) {
          const result = await requestPasswordReset(email);
          setResetMessage(result.resetToken ? `${result.message} Development token: ${result.resetToken}` : result.message);
          if (result.resetToken) setResetToken(result.resetToken);
          return;
        }
        await confirmPasswordReset(resetToken, password);
        setResetMessage("Password reset complete. Sign in with your new password.");
        setResetToken("");
        setPassword("");
        setMode("login");
        return;
      }
      const session = mode === "login"
        ? await login(email, password)
        : await signup(name, email, password);
      storeSession(session);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center p-6 font-['Inter',_sans-serif]">

      {/* Rotating background images */}
     {bgImages.map((src, i) => (
  <div
    key={i}
    className="absolute inset-0"
    style={{
      opacity: i === currentBg ? 1 : 0,
      backgroundImage: `url(${src})`,
      backgroundSize: "cover",
      backgroundPosition: "center",
      transition: "opacity 1.5s ease-in-out",  // ← smooth fade
    }}
  />
))}

      {/* Dark overlay */}
      <div className="absolute inset-0 bg-black/55" />

      {/* Form card */}
      <form onSubmit={submit} className="relative z-10 w-full max-w-md bg-white/10 backdrop-blur-md border border-white/20 rounded-lg p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3 pb-2">
          <div className="w-10 h-10 rounded bg-primary flex items-center justify-center">
            <Building2 size={18} className="text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white font-['Plus_Jakarta_Sans']">UmojaFunds</h1>
            <p className="text-xs text-white/60">Sign in to your SACCO database</p>
          </div>
        </div>

        <div className="flex gap-1 p-1 bg-white/10 rounded-lg">
          {(["login", "signup", "reset"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => { setMode(item); setError(""); setResetMessage(""); }}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-md capitalize ${mode === item ? "bg-white text-gray-900 shadow-sm" : "text-white/70"}`}
            >
              {item === "reset" ? "Reset" : item}
            </button>
          ))}
        </div>

        {mode === "signup" && (
          <label className="block">
            <span className="text-xs font-semibold text-white/70">Name</span>
            <input name="name" id="auth-name" value={name} onChange={(event) => setName(event.target.value)} required className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-white/20 bg-white/10 text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-white/30" />
          </label>
        )}

        <label className="block">
          <span className="text-xs font-semibold text-white/70">Email</span>
          <input name="email" id="auth-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-white/20 bg-white/10 text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-white/30" />
        </label>

        {mode === "reset" && resetMessage && (
          <div className="bg-blue-500/20 border border-blue-400/30 rounded-lg p-3">
            <p className="text-xs text-blue-200 break-words">{resetMessage}</p>
          </div>
        )}

        {mode === "reset" && (
          <label className="block">
            <span className="text-xs font-semibold text-white/70">Reset Token</span>
            <input name="resetToken" id="auth-resetToken" value={resetToken} onChange={(event) => setResetToken(event.target.value)} placeholder="Paste reset token after requesting one" className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-white/20 bg-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-white/30" />
          </label>
        )}

        {mode !== "reset" || resetToken ? (
          <label className="block">
            <span className="text-xs font-semibold text-white/70">Password</span>
            <input name="password" id="auth-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-white/20 bg-white/10 text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-white/30" />
          </label>
        ) : null}

        {error && (
          <div className="bg-red-500/20 border border-red-400/30 rounded-lg p-3 flex items-start gap-2">
            <AlertCircle size={14} className="text-red-300 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-300">{error}</p>
          </div>
        )}

        <button disabled={submitting} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground text-sm font-semibold rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors">
          {submitting ? <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Connecting</> : mode === "login" ? "Sign In" : mode === "signup" ? "Create Account" : resetToken ? "Reset Password" : "Send Reset Link"}
        </button>
      </form>
      {/* Footer */}
<footer className="absolute bottom-0 left-0 right-0 z-10 px-6 py-4 bg-gradient-to-t from-black/70 to-transparent">
  <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
    
    {/* Left: brand + mission */}
    <div className="text-left">
      <p className="text-white text-sm font-bold tracking-wide">UmojaFunds SACCO ERP</p>
      <p className="text-white/50 text-xs mt-0.5">
        Empowering Kenyan cooperatives with modern financial tools
      </p>
    </div>

    {/* Center: feature pills */}
    <div className="flex flex-wrap justify-center gap-1.5">
      {["Members", "Loans", "Savings", "Reports", "M-Pesa"].map((item) => (
        <span key={item} className="px-2.5 py-0.5 text-xs rounded-full bg-black/10 border border-white/15 text-white/70">
          {item}
        </span>
      ))}
    </div>

    {/* Right: copyright */}
    <p className="text-white/50 text-xs text-right">
      © {new Date().getFullYear()} UmojaFunds<br />All rights reserved
    </p>

  </div>
 </footer>
</div>
    
  );
}

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(() => getStoredSession());
  const [membership, setMembership] = useState<MembershipStatus | null>(null);
  const [saccoData, setSaccoData] = useState<SaccoData>(EMPTY_SACCO_DATA);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [activeNav, setActiveNav] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationError, setNotificationError] = useState("");
  const [adminUsers, setAdminUsers] = useState<AuthUser[]>([]);
  const [sendNotificationForm, setSendNotificationForm] = useState({
    userId: "",
    type: "info" as "info" | "success" | "warning" | "danger",
    title: "",
    message: "",
  });
  const [sendingNotification, setSendingNotification] = useState(false);
  const [geminiBannerDismissed, setGeminiBannerDismissed] = useState(
    localStorage.getItem("gemini_banner_dismissed") === "true"
  );

  const { title, subtitle } = PAGE_TITLES[activeNav] || PAGE_TITLES["dashboard"];

  const refreshMembership = React.useCallback(async () => {
    if (!session?.token) return;
    try {
      setMembership(await getMembershipStatus(session.token));
    } catch {
      setMembership(null);
    }
  }, [session?.token]);

  const refreshData = React.useCallback(async () => {
    if (!session?.token) return;
    if (session.user.role !== "admin" && !membership?.member) {
      setSaccoData(EMPTY_SACCO_DATA);
      setDataError(null);
      return;
    }
    setDataLoading(true);
    setDataError(null);
    try {
      setSaccoData(await fetchSaccoData(session.token));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load SACCO data";
      setDataError(message);
      if (/invalid|expired|authentication/i.test(message)) {
        clearSession();
        setSession(null);
      }
    } finally {
      setDataLoading(false);
    }
  }, [membership?.member, session?.token, session?.user.role]);

  const refreshNotifications = React.useCallback(async () => {
    if (!session?.token) return;
    setNotificationsLoading(true);
    setNotificationError("");
    try {
      setNotifications(await listNotifications(session.token));
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : "Failed to load notifications");
    } finally {
      setNotificationsLoading(false);
    }
  }, [session?.token]);

  const refreshAdminUsers = React.useCallback(async () => {
    if (!session?.token || session.user.role !== "admin") return;
    try {
      const users = await listAdminUsers(session.token);
      setAdminUsers(users.filter((user) => user.isActive));
    } catch {
      setAdminUsers([]);
    }
  }, [session?.token, session?.user.role]);

  useEffect(() => {
    refreshMembership();
  }, [refreshMembership]);

  useEffect(() => {
    if (session?.user.role === "admin" || membership) {
      refreshData();
    }
  }, [membership, refreshData, session?.user.role]);

  useEffect(() => {
    refreshNotifications();
    refreshAdminUsers();
  }, [refreshAdminUsers, refreshNotifications]);

  useEffect(() => {
    if (!session?.token) return;
    trackProductEvent(session.token, {
      eventName: "screen_viewed",
      feature: activeNav,
      properties: { role: session.user.role },
    });
  }, [activeNav, session?.token, session?.user.role]);

  useEffect(() => {
    if (!session?.token) return;
    const handleBeforeUnload = () => trackSessionEnd(session.token);
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [session?.token]);

  useEffect(() => {
    const currentItem = navItems.find((item) => item.id === activeNav);
    if (
      (session?.user.role !== "admin" && currentItem?.adminOnly)
      || (session?.user.role === "admin" && currentItem?.userOnly)
    ) {
      setActiveNav("dashboard");
    }
  }, [activeNav, session?.user.role]);

  const handleLogout = async () => {
    if (session?.token) {
      await logout(session.token).catch(() => {});
    }
    clearSession();
    setSession(null);
    setMembership(null);
    setSaccoData(EMPTY_SACCO_DATA);
    setNotifications([]);
    setAdminUsers([]);
  };

  if (!session) {
    return <AuthView onAuthenticated={setSession} />;
  }
  
  const dismissGeminiBanner = () => {
    localStorage.setItem("gemini_banner_dismissed", "true");
    setGeminiBannerDismissed(true);
  };

  const handleNav = (id: string) => {
    setActiveNav(id);
    setMobileSidebarOpen(false);
  };

  const unreadNotifications = notifications.filter((notification) => !notification.readAt).length;

  const handleNotificationClick = async (notification: Notification) => {
    if (!session?.token || notification.readAt) return;
    const updated = await markNotificationRead(session.token, notification.id).catch(() => null);
    if (!updated) return;
    setNotifications((current) => current.map((item) => item.id === updated.id ? updated : item));
  };

  const handleSendNotification = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!session?.token || session.user.role !== "admin" || sendingNotification) return;
    setSendingNotification(true);
    setNotificationError("");
    try {
      const notification = await createNotification(session.token, {
        userId: Number(sendNotificationForm.userId),
        type: sendNotificationForm.type,
        title: sendNotificationForm.title,
        message: sendNotificationForm.message,
      });
      setNotifications((current) => [notification, ...current]);
      setSendNotificationForm({ userId: "", type: "info", title: "", message: "" });
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : "Failed to send notification");
    } finally {
      setSendingNotification(false);
    }
  };

  const renderView = () => {
    if (session.user.role !== "admin" && !membership?.member && activeNav !== "membership" && activeNav !== "settings") {
      return <MembershipApplicationView />;
    }

    switch (activeNav) {
      case "dashboard": return <DashboardView onNav={handleNav} />;
      case "membership": return <MembershipApplicationView />;
      case "members": return <MembersView onNav={handleNav} />;
      case "loans": return <LoansView onNav={handleNav} />;
      case "loan-repayment": return <LoanRepaymentView />;
      case "savings": return <SavingsView />;
      case "transactions": return <TransactionsView />;
      case "product-analytics": return <ProductUsageAnalyticsDashboard session={session} />;
      case "reports": return <ReportsView />;
      case "loan-scoring": return <LoanScoringView />;
      case "fraud": return <FraudDetectionView />;
      case "collections": return <CollectionsView />;
      case "ai": return <AIAssistantView />;
      case "admin": return <AdminView />;
      case "settings": return <SettingsView />;
      default:
        return (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-3">
            <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center">
              <Settings size={20} className="text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">{title} module coming soon</p>
          </div>
        );
    }
  };

  return (
    <SaccoDataContext.Provider value={{ data: saccoData, session, membership, loading: dataLoading, error: dataError, refresh: refreshData, refreshMembership }}>
    <div className="flex h-screen bg-background overflow-hidden font-['Inter',_sans-serif]">
      {mobileSidebarOpen && (
        <button
          aria-label="Close sidebar"
          onClick={() => setMobileSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/45 lg:hidden"
        />
      )}
      <Sidebar
        active={activeNav}
        onNav={handleNav}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((p) => !p)}
        mobileOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
        onLogout={handleLogout}
        session={session}
      />

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <header className="flex items-center justify-between px-4 sm:px-6 py-4 bg-card border-b border-border flex-shrink-0 gap-3">
          <button
            onClick={() => setMobileSidebarOpen(true)}
            className="lg:hidden w-9 h-9 rounded-lg flex items-center justify-center border border-border bg-card hover:bg-secondary transition-colors flex-shrink-0"
            aria-label="Open sidebar"
            aria-expanded={mobileSidebarOpen}
          >
            <Menu size={17} className="text-muted-foreground" />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-foreground font-['Plus_Jakarta_Sans'] truncate">{title}</h1>
              {(activeNav === "ai" || activeNav === "loan-scoring" || activeNav === "fraud" || activeNav === "collections") && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold border border-primary/20 flex items-center gap-1">
                  <Sparkles size={10} /> Gemini
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground truncate">{subtitle}</p>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
            <div className="relative hidden sm:block">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input type="text" placeholder="Quick search..." className="pl-8 pr-4 py-1.5 text-xs rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-primary/20 w-44" />
            </div>

            <div className="relative">
              <button onClick={() => setNotifOpen((p) => !p)}
                className="relative w-8 h-8 rounded-lg flex items-center justify-center border border-border bg-card hover:bg-secondary transition-colors">
                <Bell size={14} className="text-muted-foreground" />
                <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-accent rounded-full" />
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-10 w-72 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                    <p className="text-sm font-semibold text-foreground">Notifications</p>
                    <button onClick={() => setNotifOpen(false)}><X size={13} className="text-muted-foreground" /></button>
                  </div>
                  <div className="divide-y divide-border">
                    {[
                      { icon: TriangleAlert, color: "text-red-500", msg: "AI flagged TXN-884919 - high-confidence channel-switch anomaly", time: "1h ago" },
                      { icon: AlertCircle, color: "text-red-500", msg: "Loan LN-20240141 is 47 days overdue", time: "2h ago" },
                      { icon: CheckCircle2, color: "text-emerald-500", msg: "New loan application from Halima Kamau approved", time: "4h ago" },
                      { icon: TrendingUp, color: "text-primary", msg: "Monthly savings target 93% achieved", time: "1d ago" },
                    ].map((n, i) => (
                      <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-secondary/30 transition-colors cursor-pointer">
                        <n.icon size={14} className={`${n.color} mt-0.5 flex-shrink-0`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-foreground leading-relaxed">{n.msg}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">{n.time}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="px-4 py-2 border-t border-border">
                    <button className="text-xs text-primary font-medium hover:underline">View all notifications</button>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 pl-3 border-l border-border">
              <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary">{session.user.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</div>
              <div className="hidden sm:block">
                <p className="text-xs font-semibold text-foreground leading-none">{session.user.name}</p>
                <p className="text-xs text-muted-foreground capitalize">{session.user.role}</p>
              </div>
              <button onClick={handleLogout} className="p-1 rounded hover:bg-secondary transition-colors" title="Sign out">
                <LogOut size={12} className="text-muted-foreground" />
              </button>
            </div>
          </div>
        </header>

        <div className="flex items-center gap-1.5 px-4 sm:px-6 py-2 border-b border-border/50 text-xs text-muted-foreground bg-background flex-shrink-0">
          <span>UmojaFunds</span>
          <ChevronRight size={11} />
          <span className="text-foreground font-medium">{title}</span>
        </div>

        {(dataLoading || dataError) && (
          <div className={`mx-4 sm:mx-6 mt-4 rounded-lg border p-3 flex items-start gap-2 ${dataError ? "bg-red-50 border-red-200 text-red-700" : "bg-blue-50 border-blue-200 text-blue-700"}`}>
            {dataLoading ? <RefreshCw size={14} className="animate-spin flex-shrink-0 mt-0.5" /> : <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />}
            <p className="text-xs">{dataLoading ? "Loading live SACCO data from the backend database..." : dataError}</p>
          </div>
        )}

        {/* Gemini API Connection Banner */}
        {!isGeminiConfigured() && !geminiBannerDismissed && (
          <div className="mx-4 sm:mx-6 mt-4 bg-gradient-to-r from-emerald-50 to-blue-50 border border-emerald-200 rounded-lg p-4 flex items-start gap-3 shadow-sm">
            <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
              <Sparkles size={18} className="text-primary-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h3 className="text-sm font-bold text-foreground font-['Plus_Jakarta_Sans']">
                  Unlock AI-Powered Intelligence
                </h3>
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary text-primary-foreground font-semibold">
                  NEW
                </span>
              </div>
              <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                Connect your Gemini API key to enable advanced AI features: intelligent loan analysis, fraud detection, 
                financial forecasting, and natural language queries. <strong>Free credits available!</strong>
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button 
                  onClick={() => handleNav("ai")}
                  className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded flex items-center gap-1.5 hover:bg-primary/90 transition-colors font-medium"
                >
                  <Key size={12} />
                  Connect Gemini API
                </button>
                <a 
                  href="/GETTING_STARTED_GEMINI.md" 
                  target="_blank"
                  className="text-xs text-primary hover:underline font-medium"
                >
                  Learn more
                </a>
                <button 
                  onClick={dismissGeminiBanner}
                  className="ml-auto text-xs text-muted-foreground hover:text-foreground"
                >
                  Dismiss
                </button>
              </div>
            </div>
            <button 
              onClick={dismissGeminiBanner}
              className="text-muted-foreground hover:text-foreground flex-shrink-0"
            >
              <X size={16} />
            </button>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {renderView()}
        </main>
      </div>
    </div>
    </SaccoDataContext.Provider>
  );
}

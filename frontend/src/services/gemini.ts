/**
 * Gemini AI Service for UmojaFunds SACCO ERP.
 *
 * SECURITY NOTE:
 * In production, Gemini calls are routed through a backend endpoint
 * that protects the API key. The frontend no longer handles the API key directly.
 */

import { getStoredSession } from "./api";

interface SaccoContext {
  members?: any[];
  loans?: any[];
  transactions?: any[];
  portfolioData?: any[];
  memberProfiles?: Record<string, any>;
  anomalyFlags?: Record<string, any>;
  currentYear?: number;
}

function buildSaccoContext(context: SaccoContext): string {
  let contextStr = "You are UmojaAI, an expert AI assistant for UmojaFunds SACCO (Savings and Credit Cooperative) in Kenya.\n\n";
  contextStr += "CONTEXT ABOUT UMOJAFUNDS:\n";
  contextStr += "- A cooperative finance organization serving East African members\n";
  contextStr += "- Operates in Kenyan Shillings (KES)\n";
  contextStr += "- Integrated with M-Pesa for mobile money transactions\n";
  contextStr += "- Regulated by SASRA (Sacco Societies Regulatory Authority)\n\n";
  contextStr += `SOURCE OF TRUTH: Use only the backend SACCO data supplied below. Do not use demo/sample figures, old 2024 data, or invented member/loan/transaction records. Current year: ${context.currentYear ?? 2026}.\n\n`;

  if (context.members?.length) {
    const activeCt = context.members.filter((member) => member.status === "Active").length;
    const totalSavings = context.members.reduce((sum, member) => sum + member.savings, 0);
    const totalLoans = context.members.reduce((sum, member) => sum + member.loans, 0);
    contextStr += `MEMBER DATA (${context.members.length} members):\n`;
    contextStr += `- Active: ${activeCt}\n`;
    contextStr += `- Total savings: KES ${(totalSavings / 1000000).toFixed(2)}M\n`;
    contextStr += `- Total loans outstanding: KES ${(totalLoans / 1000000).toFixed(2)}M\n\n`;
  }

  if (context.loans?.length) {
    const activeLoans = context.loans.filter((loan) => loan.status === "Active");
    const overdueLoans = context.loans.filter((loan) => loan.status === "Overdue");
    const totalDisbursed = context.loans.reduce((sum, loan) => sum + loan.amount, 0);
    const totalBalance = context.loans.reduce((sum, loan) => sum + loan.balance, 0);
    contextStr += `LOAN PORTFOLIO (${context.loans.length} loans):\n`;
    contextStr += `- Active loans: ${activeLoans.length}\n`;
    contextStr += `- Overdue loans: ${overdueLoans.length}\n`;
    contextStr += `- Total disbursed: KES ${(totalDisbursed / 1000000).toFixed(2)}M\n`;
    contextStr += `- Outstanding balance: KES ${(totalBalance / 1000000).toFixed(2)}M\n`;
    if (overdueLoans.length) {
      contextStr += "\nOVERDUE LOANS DETAIL:\n";
      overdueLoans.forEach((loan) => {
        contextStr += `- ${loan.id}: ${loan.member}, KES ${loan.balance.toLocaleString()} overdue\n`;
      });
    }
    contextStr += "\n";
  }

  if (context.transactions?.length) {
    const recentTxns = context.transactions.slice(0, 20);
    const creditVol = recentTxns.filter((txn) => txn.type === "Credit").reduce((sum, txn) => sum + txn.amount, 0);
    const debitVol = recentTxns.filter((txn) => txn.type === "Debit").reduce((sum, txn) => sum + txn.amount, 0);
    contextStr += `RECENT TRANSACTIONS (last ${recentTxns.length}):\n`;
    contextStr += `- Credit volume: KES ${(creditVol / 1000000).toFixed(2)}M\n`;
    contextStr += `- Debit volume: KES ${(debitVol / 1000000).toFixed(2)}M\n`;
    contextStr += `- Net flow: KES ${((creditVol - debitVol) / 1000000).toFixed(2)}M\n\n`;
    contextStr += "RECENT TRANSACTION DETAIL:\n";
    recentTxns.forEach((txn) => {
      contextStr += `- ${txn.id}: ${txn.member}, ${txn.type} KES ${txn.amount.toLocaleString()}, ${txn.category}, ${txn.channel}, ${txn.date}\n`;
    });
    contextStr += "\n";
  }

  if (context.portfolioData?.length) {
    const latest = context.portfolioData[context.portfolioData.length - 1];
    contextStr += "LATEST PORTFOLIO SNAPSHOT:\n";
    contextStr += `- Month: ${latest.month}\n`;
    contextStr += `- Savings: KES ${(latest.savings / 1000000).toFixed(2)}M\n`;
    contextStr += `- Loans: KES ${(latest.loans / 1000000).toFixed(2)}M\n`;
    contextStr += `- Repayments: KES ${(latest.repayments / 1000000).toFixed(2)}M\n\n`;
  }

  if (context.anomalyFlags && Object.keys(context.anomalyFlags).length) {
    contextStr += "BACKEND ANOMALY FLAGS:\n";
    Object.entries(context.anomalyFlags).forEach(([transactionId, flag]) => {
      contextStr += `- ${transactionId}: ${flag.level} - ${flag.reason}\n`;
    });
    contextStr += "\n";
  }

  contextStr += "IMPORTANT INSTRUCTIONS:\n";
  contextStr += "- Always reference amounts in Kenyan Shillings (KES)\n";
  contextStr += "- Use M for millions (e.g., KES 1.2M)\n";
  contextStr += "- If exact data is unavailable in the backend context, say so instead of guessing\n";
  contextStr += "- Use 2026 when naming the current year unless a backend record explicitly contains another date\n";
  contextStr += "- Reference SASRA regulatory standards when discussing NPL ratios (3.5% threshold)\n";
  contextStr += "- Be specific with member names, loan IDs, and transaction references\n";
  contextStr += "- Provide actionable recommendations for SACCO administrators\n";
  contextStr += "- Consider M-Pesa integration when discussing payment channels\n";
  contextStr += "- Format responses in clear Markdown with bullet points and sections\n";
  contextStr += "- Be concise but thorough; SACCO admins need quick insights\n";

  return contextStr;
}

function toGeminiRole(role: "user" | "assistant"): "user" | "model" {
  return role === "assistant" ? "model" : "user";
}

/**
 * Send a message to the Gemini AI model via the backend proxy.
 * The backend proxy handles the API key and forwards the request to Gemini.
 */
export async function sendGeminiMessage(
  userMessage: string,
  saccoContext: SaccoContext = {},
  conversationHistory: Array<{ role: "user" | "assistant"; content: string }> = [],
): Promise<string> {
  const session = getStoredSession();
  if (!session?.token) {
    throw new Error("Please sign in before using the AI assistant.");
  }

  // Call the backend proxy endpoint
  const response = await fetch(`/api/ai-proxy/gemini/generateContent`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${session.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      systemInstruction: {
        parts: [{ text: buildSaccoContext(saccoContext) }],
      },
      contents: [
        ...conversationHistory.map((message) => ({
          role: toGeminiRole(message.role),
          parts: [{ text: message.content }],
        })),
        {
          role: "user",
          parts: [{ text: userMessage }],
        },
      ],
      generationConfig: {
        temperature: 0.3,
        maxOutputTokens: 2048,
      },
    }),
  });

  if (!response.ok) {
    let detail = await response.text();
    try {
      const payload = JSON.parse(detail);
      detail = payload.detail || payload.error?.message || detail;
    } catch {
      // Keep the raw provider response.
    }
    throw Object.assign(new Error(detail), { status: response.status });
  }

  const payload = await response.json();
  const text = payload.candidates?.[0]?.content?.parts
    ?.map((part: { text?: string }) => part.text || "")
    .join("")
    .trim();

  if (!text) {
    throw new Error("Gemini returned an empty response. Please try again.");
  }

  return text;
}

// These functions are kept for compatibility but are no longer used for API key management.
export function resetGeminiClient(): void {
  // No-op: API key is managed by the backend
}

export function isGeminiConfigured(): boolean {
  // Always return true if the backend is configured; actual check happens in the proxy.
  // We cannot know the backend's state from the frontend, so we assume it is configured.
  // The proxy will return an error if not configured.
  return true;
}

/**
 * Analyze a loan application using the Gemini AI model.
 */
export async function analyzeLoanApplication(memberData: any, loanAmount: number, saccoContext: SaccoContext = {}): Promise<string> {
  return sendGeminiMessage(
    `Analyze this loan application and provide a detailed assessment:\n\nAPPLICANT: ${memberData.name} (${memberData.id})\nLOAN REQUESTED: KES ${loanAmount.toLocaleString()}\n\nMEMBER DETAILS:\n- Current savings: KES ${memberData.savings.toLocaleString()}\n- Existing loans: KES ${memberData.loans.toLocaleString()}\n- Account status: ${memberData.status}\n- Member since: ${memberData.joined}\n- Share capital: ${memberData.shares} shares\n\nPlease provide risk, strengths, risk factors, recommendation, suggested rate/term, and monitoring requirements.`,
    saccoContext,
  );
}

/**
 * Detect fraud patterns in transactions using the Gemini AI model.
 */
export async function detectFraudPatterns(transactions: any[], saccoContext: SaccoContext = {}): Promise<string> {
  const txnSummary = transactions.slice(0, 10).map((txn) =>
    `${txn.id}: ${txn.member} - ${txn.type} KES ${txn.amount.toLocaleString()} (${txn.category}) via ${txn.channel}`
  ).join("\n");

  return sendGeminiMessage(
    `Analyze these recent transactions for fraud patterns:\n\n${txnSummary}\n\nIdentify suspicious patterns, risk levels, recommended admin actions, and preventive measures.`,
    saccoContext,
  );
}

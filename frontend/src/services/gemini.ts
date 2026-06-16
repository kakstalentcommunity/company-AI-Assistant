/**
 * Gemini AI Service for UmojaFunds SACCO ERP.
 *
 * This is the simplified version that uses the new /api/ai-query/chat endpoint.
 * The backend now handles Gemini function calling internally – the AI can
 * query the database (both internal SQLite models and external MySQL tables)
 * on demand.
 */

import { aiChat, getStoredSession, type AiChatMessage } from "./api";

/**
 * Send a message to the AI assistant (backed by Gemini via the backend proxy).
 * The backend handles all database queries using Gemini's function calling API.
 */
export async function sendGeminiMessage(
  userMessage: string,
  _saccoContext: unknown = {},
  conversationHistory: Array<{ role: "user" | "assistant"; content: string }> = [],
): Promise<string> {
  const session = getStoredSession();
  if (!session?.token) {
    throw new Error("Please sign in before using the AI assistant.");
  }

  const history: AiChatMessage[] = conversationHistory.map((msg) => ({
    role: msg.role,
    content: msg.content,
  }));

  const result = await aiChat(session.token, userMessage, history);

  return result.content;
}

// These functions are kept for compatibility but are no longer used for API key management.
export function resetGeminiClient(): void {
  // No-op: API key is managed by the backend
}

export function isGeminiConfigured(): boolean {
  return true;
}

/**
 * Analyze a loan application using the Gemini AI model.
 */
export async function analyzeLoanApplication(memberData: any, loanAmount: number): Promise<string> {
  return sendGeminiMessage(
    `Analyze this loan application and provide a detailed assessment:\n\nAPPLICANT: ${memberData.name} (${memberData.id})\nLOAN REQUESTED: KES ${loanAmount.toLocaleString()}\n\nMEMBER DETAILS:\n- Current savings: KES ${memberData.savings.toLocaleString()}\n- Existing loans: KES ${memberData.loans.toLocaleString()}\n- Account status: ${memberData.status}\n- Member since: ${memberData.joined}\n- Share capital: ${memberData.shares} shares\n\nPlease provide risk, strengths, risk factors, recommendation, suggested rate/term, and monitoring requirements.`,
  );
}

/**
 * Detect fraud patterns in transactions using the Gemini AI model.
 */
export async function detectFraudPatterns(transactions: any[]): Promise<string> {
  const txnSummary = transactions.slice(0, 10).map((txn) =>
    `${txn.id}: ${txn.member} - ${txn.type} KES ${txn.amount.toLocaleString()} (${txn.category}) via ${txn.channel}`
  ).join("\n");

  return sendGeminiMessage(
    `Analyze these recent transactions for fraud patterns:\n\n${txnSummary}\n\nIdentify suspicious patterns, risk levels, recommended admin actions, and preventive measures.`,
  );
}
import { trackProductAnalyticsEvent, type ProductAnalyticsEventPayload } from "./api";

const SESSION_KEY = "umojafunds_product_analytics_session";
const SESSION_STARTED_KEY = "umojafunds_product_analytics_started";

function getSessionId(): string {
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;

  const sessionId = `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  sessionStorage.setItem(SESSION_KEY, sessionId);
  sessionStorage.setItem(SESSION_STARTED_KEY, String(Date.now()));
  return sessionId;
}

function detectDevice(): ProductAnalyticsEventPayload["device"] {
  const agent = navigator.userAgent.toLowerCase();
  if (/iphone|ipad|ipod/.test(agent)) return "iOS";
  if (/android/.test(agent)) return "Android";
  return "Web";
}

export function buildAnalyticsEvent(payload: Omit<ProductAnalyticsEventPayload, "sessionId" | "device" | "path">): ProductAnalyticsEventPayload {
  return {
    sessionId: getSessionId(),
    device: detectDevice(),
    path: window.location.pathname || "/",
    ...payload,
  };
}

export function trackProductEvent(token: string, payload: Omit<ProductAnalyticsEventPayload, "sessionId" | "device" | "path">): void {
  trackProductAnalyticsEvent(token, buildAnalyticsEvent(payload)).catch(() => {
    // Analytics should never interrupt member workflows.
  });
}

export function trackSessionEnd(token: string): void {
  const startedAt = Number(sessionStorage.getItem(SESSION_STARTED_KEY) || Date.now());
  const durationSeconds = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
  trackProductEvent(token, {
    eventName: "session_end",
    feature: "general",
    durationSeconds,
  });
}

# Product Usage Analytics

Admin-only analytics for SACCO ERP product adoption, loan funnel conversion, friction points, anomaly alerts, and AI pattern insights.

## Database Schema

`product_analytics_events`

| Column | Purpose |
| --- | --- |
| `id` | Primary key |
| `user_id` | Optional authenticated user id |
| `session_id` | Stable client session identifier |
| `event_name` | `screen_viewed`, `feature_used`, `loan_application_step`, `session_end`, `error` |
| `feature` | `balance_check`, `loans`, `chatbot`, `statements`, or app screen id |
| `funnel_name` | `loan_application` for funnel events |
| `funnel_step` | `started`, `eligibility_checked`, `documents_uploaded`, `guarantors_added`, `submitted`, `approved` |
| `device` | `Android`, `iOS`, `Web`, `USSD` |
| `path` | Client route or channel path |
| `duration_seconds` | Optional action/session duration |
| `properties_json` | Non-PII JSON metadata |
| `occurred_at`, `created_at` | Event timestamps |

`product_usage_daily_metrics` stores precomputed DAU/MAU, session duration, bounce, retention, conversion, and active users for scheduled rollups.

`product_analytics_alerts` stores open/resolved anomaly alerts such as error spikes, usage dips, and funnel drop-offs.

`product_analytics_insights` stores AI-generated insight narratives and recommendations.

## API Endpoints

`POST /api/analytics/events`

Authenticated event ingestion for web/mobile/USSD channels.

```json
{
  "sessionId": "web-1780000000-x9a21b",
  "eventName": "loan_application_step",
  "feature": "loans",
  "funnelName": "loan_application",
  "funnelStep": "documents_uploaded",
  "device": "Android",
  "path": "/loans/apply",
  "durationSeconds": 142,
  "properties": {
    "loanType": "Business"
  }
}
```

`GET /api/admin/analytics/dashboard?days=30`

Admin-only dashboard payload with:

- DAU/MAU, average session duration, bounce rate, retention, loan conversion
- Loan application funnel with drop-off percentages
- Feature usage table
- Friction points and AI fix recommendations
- Time series for active users and conversion trends
- Real-time anomaly alerts
- Android/iOS/Web/USSD device breakdown
- AI insights generated from observed patterns

`GET /api/admin/analytics/schema`

Admin-only event contract reference for integrators.

## Frontend Tracking Snippet

Web usage is implemented in `src/services/productAnalyticsTracking.ts`.

```ts
trackProductEvent(token, {
  eventName: "feature_used",
  feature: "balance_check",
  durationSeconds: 34,
  properties: { source: "member_dashboard" },
});

trackProductEvent(token, {
  eventName: "loan_application_step",
  feature: "loans",
  funnelName: "loan_application",
  funnelStep: "submitted",
});
```

Analytics is intentionally fire-and-forget. Failed tracking requests must not interrupt member workflows.

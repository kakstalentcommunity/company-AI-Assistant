# Intrusion Detection System

The API includes a lightweight intrusion detection system (IDS) for recording suspicious request activity without interrupting normal member or staff workflows.

## What It Detects

The IDS logs security events for:

- SQL injection, cross-site scripting, path traversal, and command injection probes in paths or query strings
- requests to common sensitive probe paths such as `.env`, `.git`, WordPress admin paths, phpMyAdmin, server status, and actuator endpoints
- known scanner user agents
- rare HTTP methods such as `TRACE` and `CONNECT`
- oversized requests rejected by request-size middleware
- rate limit responses
- denied access attempts against admin API routes
- failed login and disabled-account login attempts

The IDS is intentionally detective, not preventive. Existing controls such as authentication, role checks, request-size limits, rate limits, trusted hosts, and security headers still enforce protection.

## Database Table

`security_events`

| Column | Purpose |
| --- | --- |
| `id` | Primary key |
| `event_type` | Stable IDS event id such as `ids.sql_injection_probe` |
| `severity` | `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` |
| `user_id` | Optional authenticated or known user id |
| `ip_address` | Client IP, honoring the first `X-Forwarded-For` value |
| `user_agent` | Truncated request user agent |
| `method` | HTTP method |
| `path` | Request path |
| `status_code` | Response status when the event is response-driven |
| `details` | JSON evidence and reason |
| `created_at` | Detection timestamp |

## Admin API

`GET /api/admin/security-events`

Lists recent IDS events. Query parameters:

- `limit`: `1` to `500`, default `100`
- `severity`: optional `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`
- `eventType`: optional exact event type filter

`GET /api/admin/security-events/summary?hours=24`

Returns total IDS events, counts by severity, and top event types for the selected window.

Both endpoints require an admin session.

## Configuration

Add these values to `backend/.env` when needed:

```env
IDS_ENABLED=true
IDS_DETAIL_MAX_LENGTH=2000
MAX_REQUEST_BYTES=1000000
API_RATE_LIMIT_ATTEMPTS=120
API_RATE_LIMIT_WINDOW_SECONDS=60
AUTH_RATE_LIMIT_ATTEMPTS=5
AUTH_RATE_LIMIT_WINDOW_SECONDS=900
```

## Operational Notes

- Treat IDS events as investigation leads, not proof of compromise.
- Review `HIGH` and `CRITICAL` events first, especially repeated events from the same IP.
- Keep reverse proxy forwarding headers trustworthy. If the API is exposed through a proxy, configure the proxy to set `X-Forwarded-For` and prevent clients from spoofing it directly.
- Pair IDS review with audit logs from `GET /api/admin/audit-logs` to understand actor context.

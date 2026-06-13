import logging
from datetime import datetime, timedelta

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import (
    ANALYTICS_RATE_LIMIT_ATTEMPTS,
    API_RATE_LIMIT_ATTEMPTS,
    API_RATE_LIMIT_WINDOW_SECONDS,
    MAX_REQUEST_BYTES,
)
from app.services.ids import IDS

logger = logging.getLogger("umojafunds.api")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")

        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        return response


class IntrusionDetectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        findings = IDS.inspect_request(request)
        if findings:
            IDS.log_findings(request, findings)

        response = await call_next(request)
        IDS.log_response_signal(request, response.status_code)
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body is too large"},
                )

        return await call_next(request)


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not self._should_limit(request):
            return await call_next(request)

        allowed = self._record_request(request)
        if not allowed:
            logger.warning("Rate limit exceeded for %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again."},
            )

        return await call_next(request)

    def _should_limit(self, request: Request) -> bool:
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return False
        if not request.url.path.startswith("/api/"):
            return False
        if request.url.path.startswith("/api/auth/"):
            return False
        return True

    def _record_request(self, request: Request) -> bool:
        from app.database import SessionLocal
        from app.models.models import RateLimitEvent

        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_host = forwarded_for.split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
        auth_header = request.headers.get("authorization", "")
        user_key = auth_header[-24:] if auth_header.lower().startswith("bearer ") else client_host
        bucket = "analytics" if request.url.path.startswith("/api/analytics/") else "api"
        limit = ANALYTICS_RATE_LIMIT_ATTEMPTS if bucket == "analytics" else API_RATE_LIMIT_ATTEMPTS
        key = f"{bucket}:{request.method}:{request.url.path}:{user_key}"
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=API_RATE_LIMIT_WINDOW_SECONDS)

        db = SessionLocal()
        try:
            db.query(RateLimitEvent).filter(RateLimitEvent.created_at < window_start).delete()
            attempts = db.query(RateLimitEvent).filter(
                RateLimitEvent.key == key,
                RateLimitEvent.created_at >= window_start,
            ).count()
            if attempts >= limit:
                db.commit()
                return False
            db.add(RateLimitEvent(key=key, created_at=now))
            db.commit()
            return True
        finally:
            db.close()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code >= 400:
            logger.warning("%s %s returned %s", request.method, request.url.path, response.status_code)
        return response

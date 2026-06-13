from contextlib import asynccontextmanager
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import CORS_ORIGINS, IS_PRODUCTION, LOG_DIR, TRUSTED_HOSTS
from app.database import init_db
from app.middleware import (
    ApiRateLimitMiddleware,
    IntrusionDetectionMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.routes import auth
from app.routes import data
from app.routes import members
from app.routes import loans
from app.routes import mpesa
from app.routes import notifications
from app.routes import transactions
from app.routes import ai_scoring
from app.routes import applications
from app.routes import product_analytics
from app.routes import ai_proxy
from app.routes import security_events


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / "api.log"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", "") == str(log_path) for handler in root_logger.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root_logger.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    yield


app = FastAPI(
    title="UmojaFunds SACCO API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

logger = logging.getLogger("umojafunds.api")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ApiRateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)
app.add_middleware(IntrusionDetectionMiddleware)

app.include_router(data.router)
app.include_router(auth.router)
app.include_router(auth.admin_router)
app.include_router(members.router)
app.include_router(loans.router)
app.include_router(mpesa.router)
app.include_router(notifications.router)
app.include_router(notifications.admin_router)
app.include_router(transactions.router)
app.include_router(ai_scoring.router)
app.include_router(applications.router)
app.include_router(applications.admin_router)
app.include_router(product_analytics.router)
app.include_router(product_analytics.admin_router)
app.include_router(ai_proxy.router)
app.include_router(security_events.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again later."},
    )


@app.get("/")
def root():
    return {
        "message": "UmojaFunds API running",
        "docs": "/docs",
        "health": "/api/health",
        "saccoData": "/api/sacco-data",
    }

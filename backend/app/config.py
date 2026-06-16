import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=True)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

CORS_ORIGINS = _csv_env(
    "CORS_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
TRUSTED_HOSTS = _csv_env("TRUSTED_HOSTS", ["localhost", "127.0.0.1", "*.localhost"])
FRONTEND_URL = os.getenv("FRONTEND_URL", CORS_ORIGINS[0] if CORS_ORIGINS else "http://localhost:5173").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _int_env("SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME or "no-reply@umojafunds.local").strip()
SMTP_USE_TLS = _bool_env("SMTP_USE_TLS", True)

ALLOW_PUBLIC_SIGNUP = _bool_env("ALLOW_PUBLIC_SIGNUP", False)
ENV_ADMIN_LOGIN_ENABLED = _bool_env("ENV_ADMIN_LOGIN_ENABLED", False)
ENV_ADMIN_EMAIL = os.getenv("ENV_ADMIN_EMAIL", "").strip().lower()
ENV_ADMIN_PASSWORD = os.getenv("ENV_ADMIN_PASSWORD", "")
SESSION_HOURS = _int_env("SESSION_HOURS", 12)
SESSION_IDLE_MINUTES = _int_env("SESSION_IDLE_MINUTES", 30)
PASSWORD_RESET_MINUTES = _int_env("PASSWORD_RESET_MINUTES", 30)
MAX_REQUEST_BYTES = _int_env("MAX_REQUEST_BYTES", 1_000_000)
IDS_ENABLED = _bool_env("IDS_ENABLED", True)
IDS_DETAIL_MAX_LENGTH = _int_env("IDS_DETAIL_MAX_LENGTH", 2_000)

AUTH_RATE_LIMIT_ATTEMPTS = _int_env("AUTH_RATE_LIMIT_ATTEMPTS", 5)
AUTH_RATE_LIMIT_WINDOW_SECONDS = _int_env("AUTH_RATE_LIMIT_WINDOW_SECONDS", 900)
API_RATE_LIMIT_ATTEMPTS = _int_env("API_RATE_LIMIT_ATTEMPTS", 120)
API_RATE_LIMIT_WINDOW_SECONDS = _int_env("API_RATE_LIMIT_WINDOW_SECONDS", 60)
ANALYTICS_RATE_LIMIT_ATTEMPTS = _int_env("ANALYTICS_RATE_LIMIT_ATTEMPTS", 300)
LOG_DIR = Path(os.getenv("LOG_DIR", BACKEND_DIR / "logs"))

MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox").strip().lower()
MPESA_BASE_URL = os.getenv(
    "MPESA_BASE_URL",
    "https://api.safaricom.co.ke" if MPESA_ENVIRONMENT == "production" else "https://sandbox.safaricom.co.ke",
).rstrip("/")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "").strip()
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "").strip()
MPESA_BUSINESS_SHORTCODE = os.getenv("MPESA_BUSINESS_SHORTCODE", "").strip()
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "").strip()
MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "").strip()
MPESA_STK_TRANSACTION_TYPE = os.getenv("MPESA_STK_TRANSACTION_TYPE", "CustomerPayBillOnline").strip()
MPESA_REQUEST_TIMEOUT_SECONDS = _int_env("MPESA_REQUEST_TIMEOUT_SECONDS", 30)

OAUTH_PROVIDERS = {
    "google": {
        "label": "Google",
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
    "facebook": {
        "label": "Facebook",
        "client_id": os.getenv("FACEBOOK_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("FACEBOOK_CLIENT_SECRET", "").strip(),
        "authorize_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me?fields=id,name,email",
        "scope": "email,public_profile",
    },
    "microsoft": {
        "label": "Microsoft",
        "client_id": os.getenv("MICROSOFT_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", "").strip(),
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
        "scope": "openid email profile",
    },
}

if IS_PRODUCTION and any(origin == "*" for origin in CORS_ORIGINS):
    raise RuntimeError("CORS_ORIGINS cannot contain '*' in production.")

if IS_PRODUCTION and any(host == "*" for host in TRUSTED_HOSTS):
    raise RuntimeError("TRUSTED_HOSTS cannot contain '*' in production.")

if IS_PRODUCTION and os.getenv("DB_USER", "").strip().lower() == "root":
    raise RuntimeError("Production must use a least-privileged database user, not root.")

if IS_PRODUCTION and os.getenv("DB_PASSWORD", "") in {"", "123456", "password", "admin", "YOUR_PASSWORD"}:
    raise RuntimeError("Production database password is missing or too weak.")

if IS_PRODUCTION and ENV_ADMIN_LOGIN_ENABLED:
    raise RuntimeError("ENV_ADMIN_LOGIN_ENABLED cannot be used in production.")

if IS_PRODUCTION and not SMTP_HOST:
    raise RuntimeError("SMTP_HOST must be configured in production for password reset delivery.")

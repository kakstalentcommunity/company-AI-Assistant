import hashlib
import hmac
import base64
import json
import logging
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta
from time import monotonic

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import (
    AUTH_RATE_LIMIT_ATTEMPTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    ENV_ADMIN_EMAIL,
    ENV_ADMIN_LOGIN_ENABLED,
    ENV_ADMIN_PASSWORD,
    PASSWORD_RESET_MINUTES,
    SESSION_HOURS,
    SESSION_IDLE_MINUTES,
)
from app.database import get_db
from app.models.models import AuthToken, PasswordResetToken, RateLimitEvent, User

PBKDF2_ITERATIONS = 390_000

bearer_scheme = HTTPBearer(auto_error=False)
_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
_login_failure_buckets: dict[str, deque[float]] = defaultdict(deque)


def _prune_bucket(bucket: deque[float], now: float) -> None:
    while bucket and now - bucket[0] > AUTH_RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt, expected = stored_hash.split("$", 3)
        iterations = int(iteration_text)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "isActive": user.is_active,
        "createdAt": user.created_at.isoformat(),
    }


def _env_admin_enabled() -> bool:
    return ENV_ADMIN_LOGIN_ENABLED and bool(ENV_ADMIN_EMAIL) and bool(ENV_ADMIN_PASSWORD)


def _env_admin_user() -> User:
    return User(
        id=0,
        name="Environment Admin",
        email=ENV_ADMIN_EMAIL,
        password_hash="",
        role="admin",
        is_active=True,
        created_at=datetime.utcnow(),
    )


def _env_admin_secret() -> bytes:
    return hashlib.sha256(f"{ENV_ADMIN_EMAIL}:{ENV_ADMIN_PASSWORD}".encode("utf-8")).digest()


def _urlsafe_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _urlsafe_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))


def create_env_admin_token(email: str, password: str) -> str | None:
    if not _env_admin_enabled():
        return None
    if email.strip().lower() != ENV_ADMIN_EMAIL:
        return None
    if not hmac.compare_digest(password, ENV_ADMIN_PASSWORD):
        return None

    payload = {
        "sub": ENV_ADMIN_EMAIL,
        "role": "admin",
        "exp": int((datetime.utcnow() + timedelta(hours=SESSION_HOURS)).timestamp()),
    }
    payload_text = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _urlsafe_encode(payload_text)
    signature = hmac.new(_env_admin_secret(), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"envadmin.{payload_part}.{_urlsafe_encode(signature)}"


def user_from_env_admin_token(raw_token: str) -> User | None:
    if not _env_admin_enabled() or not raw_token.startswith("envadmin."):
        return None

    try:
        _, payload_part, signature_part = raw_token.split(".", 2)
        expected = hmac.new(_env_admin_secret(), payload_part.encode("ascii"), hashlib.sha256).digest()
        supplied = _urlsafe_decode(signature_part)
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(_urlsafe_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    if payload.get("sub") != ENV_ADMIN_EMAIL or payload.get("role") != "admin":
        return None
    if int(payload.get("exp", 0)) < int(datetime.utcnow().timestamp()):
        return None

    return _env_admin_user()


def create_access_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.expires_at < datetime.utcnow()).delete()
    db.add(
        AuthToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(hours=SESSION_HOURS),
        )
    )
    db.commit()
    return raw_token


def create_password_reset_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).delete()
    db.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_MINUTES),
        )
    )
    db.commit()
    return raw_token


def reset_user_password(db: Session, raw_token: str, new_password: str) -> User:
    token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash_token(raw_token)).first()
    if not token or token.used_at is not None or token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")

    user = token.user
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not active")

    user.password_hash = hash_password(new_password)
    token.used_at = datetime.utcnow()
    db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    return user


def enforce_auth_rate_limit(request: Request, db: Session = Depends(get_db)) -> None:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_host = forwarded_for.split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
    key = f"auth:{client_host}"
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS)

    db.query(RateLimitEvent).filter(RateLimitEvent.created_at < window_start).delete()
    attempts = db.query(RateLimitEvent).filter(
        RateLimitEvent.key == key,
        RateLimitEvent.created_at >= window_start,
    ).count()

    if attempts >= AUTH_RATE_LIMIT_ATTEMPTS:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
        )

    db.add(RateLimitEvent(key=key, created_at=now))
    db.commit()


def assert_login_allowed(email: str) -> None:
    key = email.strip().lower()
    if not key:
        return

    now = monotonic()
    bucket = _login_failure_buckets[key]
    _prune_bucket(bucket, now)

    if len(bucket) >= AUTH_RATE_LIMIT_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts for this account. Try again later.",
        )


def record_login_failure(email: str) -> None:
    key = email.strip().lower()
    if not key:
        return

    now = monotonic()
    bucket = _login_failure_buckets[key]
    _prune_bucket(bucket, now)
    bucket.append(now)


def clear_login_failures(email: str) -> None:
    _login_failure_buckets.pop(email.strip().lower(), None)


def require_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    env_admin = user_from_env_admin_token(credentials.credentials)
    if env_admin:
        return env_admin

    token = db.query(AuthToken).filter(AuthToken.token_hash == hash_token(credentials.credentials)).first()
    now = datetime.utcnow()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    if token.expires_at < now:
        if token:
            db.delete(token)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    last_seen = token.last_seen_at or token.created_at
    idle_expired = last_seen + timedelta(minutes=SESSION_IDLE_MINUTES) < now
    if idle_expired:
        if token:
            db.delete(token)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = token.user
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not active")

    try:
        db.execute(
            text("UPDATE auth_tokens SET last_seen_at = :now WHERE id = :id"),
            {"now": now, "id": token.id},
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logging.exception("Auth token last_seen_at update failed")
        # Do not fail authentication if token state refresh cannot be persisted.

    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user

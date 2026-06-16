import json
import secrets
import time
from urllib import error as urlerror
from urllib import parse, request

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import ALLOW_PUBLIC_SIGNUP, FRONTEND_URL, IS_PRODUCTION, OAUTH_PROVIDERS, PASSWORD_RESET_MINUTES
from app.database import get_db
from app.mail import build_password_reset_link, send_password_reset_email
from app.models.models import AuditLog, AuthToken, User
from app.schemas import AdminUserCreate, LoginRequest, PasswordResetConfirm, PasswordResetRequest, SignupRequest, UserUpdate
from app.security import (
    assert_login_allowed,
    bearer_scheme,
    clear_login_failures,
    create_access_token,
    create_env_admin_token,
    create_password_reset_token,
    enforce_auth_rate_limit,
    hash_password,
    hash_token,
    record_login_failure,
    require_admin,
    require_user,
    reset_user_password,
    serialize_user,
    user_from_env_admin_token,
    verify_password,
)
from app.security.severity import Severity
from app.serializers import serialize_audit_log
from app.services.ids import IDS

router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
_oauth_states: dict[str, tuple[str, float]] = {}
_oauth_state_ttl_seconds = 600


def _oauth_redirect(params: dict[str, str]) -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_URL}/?{parse.urlencode(params)}")


def _oauth_provider(provider: str) -> dict:
    config = OAUTH_PROVIDERS.get(provider)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OAuth provider is not supported")
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{config['label']} sign-in is not configured")
    return config


def _oauth_post_json(url: str, data: dict[str, str]) -> dict:
    encoded = parse.urlencode(data).encode("utf-8")
    req = request.Request(url, data=encoded, headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urlerror.URLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAuth provider token exchange failed") from exc


def _oauth_get_json(url: str, access_token: str) -> dict:
    req = request.Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {access_token}"})
    try:
        with request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urlerror.URLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAuth provider profile lookup failed") from exc


def _upsert_oauth_user(db: Session, email: str, name: str) -> User:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="OAuth account did not provide an email address")

    user = db.query(User).filter(User.email == normalized_email).first()
    if user:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled")
        if not user.name and name:
            user.name = name[:255]
            db.commit()
            db.refresh(user)
        return user

    user_count = db.query(User).count()
    if user_count > 0 and not ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public signup is disabled")

    user = User(
        name=(name or normalized_email.split("@", 1)[0])[:255],
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role="admin" if user_count == 0 else "staff",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request_: Request,
    _: None = Depends(enforce_auth_rate_limit),
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    user_count = db.query(User).count()
    if user_count > 0 and not ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public signup is disabled")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    role = "admin" if user_count == 0 else "staff"
    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(db, user)
    write_audit_log(db, action="auth.signup", entity_type="user", entity_id=user.id, actor=user, request=request_, after=serialize_user(user))
    db.commit()
    return {"token": token, "user": serialize_user(user)}


@router.post("/login")
def login(
    payload: LoginRequest,
    request_: Request,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    assert_login_allowed(email)

    env_admin_token = create_env_admin_token(email, payload.password)
    if env_admin_token:
        clear_login_failures(email)
        env_admin = user_from_env_admin_token(env_admin_token)
        return {"token": env_admin_token, "user": serialize_user(env_admin)}

    enforce_auth_rate_limit(request_, db)

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_login_failure(email)
        write_audit_log(db, action="auth.login_failed", entity_type="user", entity_id=email, request=request_)
        IDS.log_event(
            event_type="ids.failed_login",
            severity=Severity.MEDIUM,
            details={"email": email, "knownUser": bool(user)},
            user_id=user.id if user else None,
            request=request_,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        IDS.log_event(
            event_type="ids.disabled_account_login_attempt",
            severity=Severity.MEDIUM,
            details={"email": email},
            user_id=user.id,
            request=request_,
            status_code=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled")

    clear_login_failures(email)
    token = create_access_token(db, user)
    write_audit_log(db, action="auth.login_success", entity_type="user", entity_id=user.id, actor=user, request=request_)
    db.commit()
    return {"token": token, "user": serialize_user(user)}


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequest,
    request_: Request,
    _: None = Depends(enforce_auth_rate_limit),
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    response: dict[str, object] = {"message": "If that email exists, a password reset link will be sent."}

    if not user or not user.is_active:
        write_audit_log(db, action="auth.password_reset_requested_unknown", entity_type="user", entity_id=email, request=request_)
        db.commit()
        return response

    reset_token = create_password_reset_token(db, user)
    send_password_reset_email(user.email, reset_token)
    write_audit_log(db, action="auth.password_reset_requested", entity_type="user", entity_id=user.id, actor=user, request=request_)
    db.commit()

    if not IS_PRODUCTION:
        response["resetToken"] = reset_token
        response["resetLink"] = build_password_reset_link(reset_token)
        response["expiresInMinutes"] = PASSWORD_RESET_MINUTES

    return response


@router.post("/password-reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request_: Request,
    _: None = Depends(enforce_auth_rate_limit),
    db: Session = Depends(get_db),
):
    user = reset_user_password(db, payload.token, payload.password)
    write_audit_log(db, action="auth.password_reset_completed", entity_type="user", entity_id=user.id, actor=user, request=request_)
    db.commit()
    return {"message": "Password has been reset. Please sign in again."}


@router.get("/oauth/providers")
def oauth_providers():
    return [
        {
            "id": provider,
            "label": config["label"],
            "configured": bool(config["client_id"] and config["client_secret"]),
        }
        for provider, config in OAUTH_PROVIDERS.items()
    ]


@router.get("/oauth/{provider}/start")
def oauth_start(
    provider: str,
    request_: Request,
    _: None = Depends(enforce_auth_rate_limit),
):
    config = _oauth_provider(provider)
    state = secrets.token_urlsafe(24)
    now = time.time()
    expired_states = [key for key, (_, expires_at) in _oauth_states.items() if expires_at <= now]
    for key in expired_states:
        _oauth_states.pop(key, None)
    _oauth_states[state] = (provider, now + _oauth_state_ttl_seconds)

    redirect_uri = str(request_.url_for("oauth_callback", provider=provider))
    params = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
    }
    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "select_account"
    if provider == "microsoft":
        params["prompt"] = "select_account"

    return RedirectResponse(f"{config['authorize_url']}?{parse.urlencode(params)}")


@router.get("/oauth/{provider}/callback", name="oauth_callback")
def oauth_callback(
    provider: str,
    request_: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        return _oauth_redirect({"oauthError": error})
    if not code or not state:
        return _oauth_redirect({"oauthError": "OAuth callback is missing required parameters"})

    expected = _oauth_states.pop(state, None)
    if not expected or expected[0] != provider or expected[1] <= time.time():
        return _oauth_redirect({"oauthError": "OAuth session expired. Please try again."})

    try:
        config = _oauth_provider(provider)
        redirect_uri = str(request_.url_for("oauth_callback", provider=provider))
        token_payload = _oauth_post_json(
            config["token_url"],
            {
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAuth provider did not return an access token")

        profile = _oauth_get_json(config["userinfo_url"], str(access_token))
        email = str(profile.get("email") or profile.get("upn") or profile.get("preferred_username") or "")
        name = str(profile.get("name") or profile.get("given_name") or "")
        user = _upsert_oauth_user(db, email, name)
        token = create_access_token(db, user)
    except HTTPException as exc:
        return _oauth_redirect({"oauthError": str(exc.detail)})

    return _oauth_redirect({"oauthToken": token})


@router.get("/me")
def me(user: User = Depends(require_user)):
    return serialize_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request_: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials:
        token = db.query(AuthToken).filter(AuthToken.token_hash == hash_token(credentials.credentials)).first()
        if token:
            write_audit_log(db, action="auth.logout", entity_type="user", entity_id=token.user_id, actor=token.user, request=request_)
            db.delete(token)
        db.commit()


@admin_router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [serialize_user(user) for user in users]


@admin_router.get("/audit-logs")
def list_audit_logs(
    _: User = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    return [serialize_audit_log(log) for log in logs]


@admin_router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    request_: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    if payload.role not in {"admin", "staff"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role must be admin or staff")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit_log(db, action="admin.user_created", entity_type="user", entity_id=user.id, actor=admin, request=request_, after=serialize_user(user))
    db.commit()
    return serialize_user(user)


@admin_router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request_: Request,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    active_admin_count = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
    would_remove_active_admin = (
        user.role == "admin"
        and user.is_active
        and (
            payload.role == "staff"
            or payload.is_active is False
        )
    )

    if would_remove_active_admin and active_admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the last active admin",
        )

    if payload.is_active is False and user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admins cannot deactivate their own account",
        )

    before = serialize_user(user)

    if payload.role is not None:
        user.role = payload.role

    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    write_audit_log(
        db,
        action="admin.user_updated",
        entity_type="user",
        entity_id=user.id,
        actor=current_admin,
        request=request_,
        before=before,
        after=serialize_user(user),
    )
    db.commit()
    return serialize_user(user)

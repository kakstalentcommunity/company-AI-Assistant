from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from app.config import IDS_DETAIL_MAX_LENGTH, IDS_ENABLED
from app.database import SessionLocal
from app.models.security import SecurityEvent
from app.security.severity import Severity
from app.security.utils import get_client_ip, get_request_target, get_user_agent, truncate

logger = logging.getLogger("umojafunds.ids")


@dataclass(frozen=True)
class SecurityFinding:
    event_type: str
    severity: Severity
    reason: str
    evidence: str


_SIGNATURES: tuple[tuple[str, Severity, str, re.Pattern[str]], ...] = (
    (
        "ids.sql_injection_probe",
        Severity.HIGH,
        "SQL injection pattern in request target",
        re.compile(r"(?i)(\bunion\b\s+\bselect\b|\bor\b\s+1\s*=\s*1\b|sleep\s*\(|benchmark\s*\(|information_schema|--|/\*)"),
    ),
    (
        "ids.xss_probe",
        Severity.HIGH,
        "Cross-site scripting pattern in request target",
        re.compile(r"(?i)(<\s*script\b|javascript:|onerror\s*=|onload\s*=|document\.cookie)"),
    ),
    (
        "ids.path_traversal_probe",
        Severity.HIGH,
        "Path traversal pattern in request target",
        re.compile(r"(?i)(\.\./|\.\.\\|%2e%2e|/etc/passwd|windows/win\.ini|boot\.ini)"),
    ),
    (
        "ids.command_injection_probe",
        Severity.CRITICAL,
        "Command injection pattern in request target",
        re.compile(r"(?i)((;|\||&&)\s*(cat|curl|wget|bash|sh|powershell|cmd)\b|\$\(|`[^`]+`)"),
    ),
)

_SENSITIVE_PATH_MARKERS = (
    "/.env",
    "/.git",
    "/wp-admin",
    "/wp-login",
    "/phpmyadmin",
    "/server-status",
    "/actuator",
    "/cgi-bin",
    "/vendor/phpunit",
)
_SCANNER_USER_AGENTS = ("sqlmap", "nikto", "nmap", "masscan", "zgrab", "acunetix", "nessus", "burp")
_SUSPICIOUS_METHODS = {"CONNECT", "TRACE"}


class IDS:
    @staticmethod
    def inspect_request(request: Request) -> list[SecurityFinding]:
        if not IDS_ENABLED:
            return []

        findings: list[SecurityFinding] = []
        target = get_request_target(request)
        target_lower = target.lower()
        user_agent = get_user_agent(request)
        user_agent_lower = user_agent.lower()

        if request.method.upper() in _SUSPICIOUS_METHODS:
            findings.append(
                SecurityFinding(
                    event_type="ids.suspicious_method",
                    severity=Severity.MEDIUM,
                    reason="Rare HTTP method used against API",
                    evidence=request.method.upper(),
                )
            )

        for marker in _SENSITIVE_PATH_MARKERS:
            if marker in target_lower:
                findings.append(
                    SecurityFinding(
                        event_type="ids.sensitive_path_probe",
                        severity=Severity.HIGH,
                        reason="Request targets a sensitive or common scanner path",
                        evidence=target,
                    )
                )
                break

        for event_type, severity, reason, pattern in _SIGNATURES:
            if pattern.search(target):
                findings.append(
                    SecurityFinding(
                        event_type=event_type,
                        severity=severity,
                        reason=reason,
                        evidence=target,
                    )
                )

        if any(scanner in user_agent_lower for scanner in _SCANNER_USER_AGENTS):
            findings.append(
                SecurityFinding(
                    event_type="ids.scanner_user_agent",
                    severity=Severity.HIGH,
                    reason="Known scanner user agent observed",
                    evidence=user_agent,
                )
            )

        if len(request.url.query) > 1_500:
            findings.append(
                SecurityFinding(
                    event_type="ids.long_query_string",
                    severity=Severity.MEDIUM,
                    reason="Unusually long query string",
                    evidence=target,
                )
            )

        return findings

    @staticmethod
    def log_findings(request: Request, findings: list[SecurityFinding]) -> None:
        for finding in findings:
            IDS.log_event(
                event_type=finding.event_type,
                severity=finding.severity,
                details={
                    "reason": finding.reason,
                    "evidence": finding.evidence,
                },
                request=request,
            )

    @staticmethod
    def log_response_signal(request: Request, status_code: int) -> None:
        if not IDS_ENABLED:
            return

        if status_code == 413:
            IDS.log_event(
                event_type="ids.oversized_request",
                severity=Severity.HIGH,
                details={"reason": "Request body exceeded configured size limit"},
                request=request,
                status_code=status_code,
            )
        elif status_code == 429:
            IDS.log_event(
                event_type="ids.rate_limit_exceeded",
                severity=Severity.MEDIUM,
                details={"reason": "Request exceeded configured rate limit"},
                request=request,
                status_code=status_code,
            )
        elif status_code in {401, 403} and request.url.path.startswith("/api/admin"):
            IDS.log_event(
                event_type="ids.admin_access_denied",
                severity=Severity.MEDIUM,
                details={"reason": "Unauthorized or forbidden access attempt against admin endpoint"},
                request=request,
                status_code=status_code,
            )

    @staticmethod
    def log_event(
        event_type: str,
        severity: Severity | str,
        details: dict[str, Any] | str,
        *,
        user_id: int | None = None,
        ip_address: str | None = None,
        request: Request | None = None,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
    ) -> None:
        if not IDS_ENABLED:
            return

        normalized_severity = Severity.coerce(severity)
        details_json = IDS._details_json(details)

        if request:
            ip_address = ip_address or get_client_ip(request)
            user_agent = get_user_agent(request)
            method = method or request.method
            path = path or request.url.path
        else:
            user_agent = ""

        db = SessionLocal()
        try:
            db.add(
                SecurityEvent(
                    event_type=truncate(event_type, 100),
                    severity=normalized_severity.value,
                    user_id=user_id,
                    ip_address=truncate(ip_address or "", 100),
                    user_agent=truncate(user_agent, 255),
                    method=truncate(method or "", 10),
                    path=truncate(path or "", 255),
                    status_code=status_code,
                    details=details_json,
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Unable to persist IDS event")
        finally:
            db.close()

    @staticmethod
    def _details_json(details: dict[str, Any] | str) -> str:
        payload: dict[str, Any]
        if isinstance(details, dict):
            payload = details
        else:
            payload = {"message": details}

        serialized = json.dumps(payload, default=str)
        if len(serialized) <= IDS_DETAIL_MAX_LENGTH:
            return serialized

        compact_payload: dict[str, Any] = {"truncated": True}
        for key, value in payload.items():
            compact_payload[key] = truncate(str(value), 500) if isinstance(value, str) else value

        serialized = json.dumps(compact_payload, default=str)
        if len(serialized) <= IDS_DETAIL_MAX_LENGTH:
            return serialized

        return json.dumps({"truncated": True, "message": truncate(serialized, max(20, IDS_DETAIL_MAX_LENGTH - 40))})

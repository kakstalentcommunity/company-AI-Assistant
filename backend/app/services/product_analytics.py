from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.models import (
    LoanApplication,
    ProductAnalyticsAlert,
    ProductAnalyticsEvent,
    ProductAnalyticsInsight,
    User,
)
from app.serializers import serialize_product_alert, serialize_product_insight

FEATURE_LABELS = {
    "balance_check": "Balance check",
    "loans": "Loans",
    "chatbot": "Chatbot",
    "statements": "Statements",
}

LOAN_FUNNEL_STEPS = [
    ("started", "Application started"),
    ("eligibility_checked", "Eligibility checked"),
    ("documents_uploaded", "Documents uploaded"),
    ("guarantors_added", "Guarantors added"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
]


def _date_key(value: datetime) -> str:
    return value.date().isoformat()


def _pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _seed_events_from_existing_data(db: Session, start: datetime, end: datetime) -> list[ProductAnalyticsEvent]:
    applications = db.query(LoanApplication).filter(LoanApplication.created_at >= start).all()
    users = db.query(User).filter(User.created_at <= end).all()
    events: list[ProductAnalyticsEvent] = []

    for index, user in enumerate(users[:60]):
        occurred_at = end - timedelta(days=index % 28, hours=index % 9)
        device = ["Android", "iOS", "Web", "USSD"][index % 4]
        session_id = f"seed-{user.id}-{occurred_at.date()}"
        events.extend(
            [
                ProductAnalyticsEvent(
                    user_id=user.id,
                    session_id=session_id,
                    event_name="feature_used",
                    feature=["balance_check", "loans", "chatbot", "statements"][index % 4],
                    device=device,
                    duration_seconds=120 + (index % 8) * 35,
                    occurred_at=occurred_at,
                ),
                ProductAnalyticsEvent(
                    user_id=user.id,
                    session_id=session_id,
                    event_name="session_end",
                    feature="general",
                    device=device,
                    duration_seconds=180 + (index % 10) * 42,
                    occurred_at=occurred_at + timedelta(minutes=8),
                ),
            ]
        )

    for application in applications:
        status_steps = ["started", "eligibility_checked", "documents_uploaded", "guarantors_added", "submitted"]
        if application.status == "Approved":
            status_steps.append("approved")
        for step_index, step in enumerate(status_steps):
            events.append(
                ProductAnalyticsEvent(
                    user_id=application.user_id,
                    session_id=f"loan-app-{application.id}",
                    event_name="loan_application_step",
                    feature="loans",
                    funnel_name="loan_application",
                    funnel_step=step,
                    device=["Android", "Web", "iOS"][application.id % 3],
                    duration_seconds=90 + step_index * 45,
                    occurred_at=application.created_at + timedelta(minutes=step_index * 4),
                )
            )

    return events


def _load_events(db: Session, days: int) -> list[ProductAnalyticsEvent]:
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    events = (
        db.query(ProductAnalyticsEvent)
        .filter(ProductAnalyticsEvent.occurred_at >= start)
        .order_by(ProductAnalyticsEvent.occurred_at.asc())
        .all()
    )
    return events or _seed_events_from_existing_data(db, start, end)


def _build_kpis(events: list[ProductAnalyticsEvent]) -> dict:
    now = datetime.utcnow()
    today = now.date()
    last_30_start = today - timedelta(days=29)
    last_7_start = today - timedelta(days=6)
    previous_7_start = today - timedelta(days=13)

    users_today = {event.user_id or event.session_id for event in events if event.occurred_at.date() == today}
    users_30 = {event.user_id or event.session_id for event in events if event.occurred_at.date() >= last_30_start}
    users_last_7 = {event.user_id or event.session_id for event in events if event.occurred_at.date() >= last_7_start}
    users_previous_7 = {
        event.user_id or event.session_id
        for event in events
        if previous_7_start <= event.occurred_at.date() < last_7_start
    }

    sessions: dict[str, list[ProductAnalyticsEvent]] = defaultdict(list)
    for event in events:
        sessions[event.session_id].append(event)

    durations = []
    bounces = 0
    for session_events in sessions.values():
        durations.extend(event.duration_seconds for event in session_events if event.duration_seconds is not None)
        if len({event.event_name for event in session_events}) <= 1 or len(session_events) <= 1:
            bounces += 1

    submitted = len({event.session_id for event in events if event.funnel_step == "submitted"})
    started = len({event.session_id for event in events if event.funnel_step == "started"})

    return {
        "dau": len(users_today),
        "mau": len(users_30),
        "avgSessionDurationSeconds": round(sum(durations) / len(durations)) if durations else 0,
        "bounceRate": _pct(bounces, len(sessions)),
        "retentionRate": _pct(len(users_last_7 & users_previous_7), len(users_previous_7)),
        "conversionRate": _pct(submitted, started),
    }


def _build_time_series(events: list[ProductAnalyticsEvent], days: int) -> list[dict]:
    today = datetime.utcnow().date()
    series = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_events = [event for event in events if event.occurred_at.date() == day]
        active_users = len({event.user_id or event.session_id for event in day_events})
        started = len({event.session_id for event in day_events if event.funnel_step == "started"})
        submitted = len({event.session_id for event in day_events if event.funnel_step == "submitted"})
        series.append(
            {
                "date": day.isoformat(),
                "activeUsers": active_users,
                "conversionRate": _pct(submitted, started),
                "dropOffRate": round(100 - _pct(submitted, started), 1) if started else 0,
            }
        )
    return series


def _build_feature_usage(events: list[ProductAnalyticsEvent]) -> list[dict]:
    feature_events = [event for event in events if event.feature in FEATURE_LABELS]
    totals = Counter(event.feature for event in feature_events)
    users_by_feature: dict[str, set] = defaultdict(set)
    durations_by_feature: dict[str, list[int]] = defaultdict(list)

    for event in feature_events:
        users_by_feature[event.feature].add(event.user_id or event.session_id)
        if event.duration_seconds is not None:
            durations_by_feature[event.feature].append(event.duration_seconds)

    total_events = sum(totals.values()) or 1
    rows = []
    for feature, label in FEATURE_LABELS.items():
        durations = durations_by_feature[feature]
        usage_count = totals[feature]
        rows.append(
            {
                "feature": feature,
                "label": label,
                "usageCount": usage_count,
                "uniqueUsers": len(users_by_feature[feature]),
                "adoptionRate": _pct(usage_count, total_events),
                "avgDurationSeconds": round(sum(durations) / len(durations)) if durations else 0,
                "trend": "up" if usage_count >= max(1, total_events / len(FEATURE_LABELS)) else "down",
            }
        )
    return rows


def _build_funnel(events: list[ProductAnalyticsEvent]) -> list[dict]:
    sessions_by_step = {
        step: {event.session_id for event in events if event.funnel_name == "loan_application" and event.funnel_step == step}
        for step, _ in LOAN_FUNNEL_STEPS
    }
    started = len(sessions_by_step["started"]) or max(len(next(iter(sessions_by_step.values()), set())), 1)
    previous = started
    rows = []

    for step, label in LOAN_FUNNEL_STEPS:
        users = len(sessions_by_step[step])
        rows.append(
            {
                "step": step,
                "label": label,
                "users": users,
                "conversionFromStart": _pct(users, started),
                "dropOffFromPrevious": round(100 - _pct(users, previous), 1) if previous else 0,
            }
        )
        previous = users or previous
    return rows


def _build_device_breakdown(events: list[ProductAnalyticsEvent]) -> list[dict]:
    counts = Counter(event.device for event in events)
    total = sum(counts.values()) or 1
    return [
        {"device": device, "sessions": counts[device], "share": _pct(counts[device], total)}
        for device in ["Android", "iOS", "Web", "USSD"]
    ]


def _build_friction_points(funnel: list[dict], feature_usage: list[dict]) -> list[dict]:
    friction = []
    worst_step = max(funnel[1:], key=lambda row: row["dropOffFromPrevious"], default=None)
    if worst_step and worst_step["dropOffFromPrevious"] >= 20:
        friction.append(
            {
                "area": worst_step["label"],
                "severity": "high" if worst_step["dropOffFromPrevious"] >= 35 else "medium",
                "signal": f"{worst_step['dropOffFromPrevious']}% drop-off from the previous loan step.",
                "aiRecommendation": "Add inline validation, pre-fill known member details, and trigger a chatbot assist when members pause on this step.",
            }
        )

    for feature in feature_usage:
        if feature["trend"] == "down":
            friction.append(
                {
                    "area": feature["label"],
                    "severity": "medium",
                    "signal": f"Only {feature['adoptionRate']}% of tracked usage lands here.",
                    "aiRecommendation": "Review navigation labels, shorten the workflow, and add contextual prompts from the dashboard and mobile menu.",
                }
            )
    return friction[:5]


def _computed_alerts(kpis: dict, funnel: list[dict], time_series: list[dict]) -> list[dict]:
    alerts = []
    latest = time_series[-1] if time_series else {"dropOffRate": 0, "activeUsers": 0}
    previous = time_series[-8:-1] if len(time_series) > 7 else time_series[:-1]
    avg_previous_users = sum(point["activeUsers"] for point in previous) / len(previous) if previous else latest["activeUsers"]

    if kpis["bounceRate"] >= 45:
        alerts.append(
            {
                "id": 0,
                "severity": "high",
                "title": "Bounce rate above operating threshold",
                "description": "Members are leaving after a single product action more often than expected.",
                "metric": "bounce_rate",
                "currentValue": kpis["bounceRate"],
                "thresholdValue": 45,
                "status": "Open",
                "detectedAt": datetime.utcnow().isoformat(),
            }
        )
    if latest["activeUsers"] < avg_previous_users * 0.65:
        alerts.append(
            {
                "id": 0,
                "severity": "medium",
                "title": "Active user anomaly detected",
                "description": "Today's active usage is materially below the recent seven-day baseline.",
                "metric": "active_users",
                "currentValue": latest["activeUsers"],
                "thresholdValue": round(avg_previous_users * 0.65, 1),
                "status": "Open",
                "detectedAt": datetime.utcnow().isoformat(),
            }
        )

    worst = max(funnel[1:], key=lambda row: row["dropOffFromPrevious"], default=None)
    if worst and worst["dropOffFromPrevious"] >= 35:
        alerts.append(
            {
                "id": 0,
                "severity": "high",
                "title": "Loan funnel drop-off spike",
                "description": f"{worst['label']} is causing a {worst['dropOffFromPrevious']}% step drop-off.",
                "metric": "loan_funnel_dropoff",
                "currentValue": worst["dropOffFromPrevious"],
                "thresholdValue": 35,
                "status": "Open",
                "detectedAt": datetime.utcnow().isoformat(),
            }
        )
    return alerts


def _build_insights(kpis: dict, funnel: list[dict], feature_usage: list[dict], device_breakdown: list[dict]) -> list[dict]:
    top_device = max(device_breakdown, key=lambda row: row["sessions"], default={"device": "Web", "share": 0})
    top_feature = max(feature_usage, key=lambda row: row["usageCount"], default={"label": "Balance check"})
    worst_step = max(funnel[1:], key=lambda row: row["dropOffFromPrevious"], default={"label": "Submitted", "dropOffFromPrevious": 0})

    return [
        {
            "id": 0,
            "category": "Activation",
            "title": "Loan application completion can improve",
            "narrative": f"The largest loan journey loss is around {worst_step['label']} with {worst_step['dropOffFromPrevious']}% step drop-off.",
            "recommendation": "Prioritize a guided loan checklist and save-progress recovery messages for members who abandon this point.",
            "confidence": 88,
            "generatedAt": datetime.utcnow().isoformat(),
        },
        {
            "id": 0,
            "category": "Engagement",
            "title": f"{top_feature['label']} is the dominant product habit",
            "narrative": f"{top_feature['label']} leads feature usage while average session duration is {kpis['avgSessionDurationSeconds']} seconds.",
            "recommendation": "Place loan prompts and statement shortcuts near this feature to convert frequent intent into deeper usage.",
            "confidence": 84,
            "generatedAt": datetime.utcnow().isoformat(),
        },
        {
            "id": 0,
            "category": "Channel",
            "title": f"{top_device['device']} carries the largest usage share",
            "narrative": f"{top_device['device']} accounts for {top_device['share']}% of tracked sessions across SACCO channels.",
            "recommendation": "Tune performance budgets, copy length, and fallback flows around this dominant channel first.",
            "confidence": 81,
            "generatedAt": datetime.utcnow().isoformat(),
        },
    ]


def build_product_analytics_dashboard(db: Session, days: int = 30) -> dict:
    safe_days = max(7, min(days, 90))
    events = _load_events(db, safe_days)
    kpis = _build_kpis(events)
    time_series = _build_time_series(events, safe_days)
    feature_usage = _build_feature_usage(events)
    funnel = _build_funnel(events)
    device_breakdown = _build_device_breakdown(events)
    friction_points = _build_friction_points(funnel, feature_usage)

    stored_alerts = (
        db.query(ProductAnalyticsAlert)
        .filter(ProductAnalyticsAlert.status == "Open")
        .order_by(ProductAnalyticsAlert.detected_at.desc())
        .limit(5)
        .all()
    )
    stored_insights = (
        db.query(ProductAnalyticsInsight)
        .order_by(ProductAnalyticsInsight.generated_at.desc())
        .limit(3)
        .all()
    )

    return {
        "kpis": kpis,
        "funnel": funnel,
        "featureUsage": feature_usage,
        "frictionPoints": friction_points,
        "timeSeries": time_series,
        "alerts": [serialize_product_alert(alert) for alert in stored_alerts] or _computed_alerts(kpis, funnel, time_series),
        "deviceBreakdown": device_breakdown,
        "insights": [serialize_product_insight(insight) for insight in stored_insights] or _build_insights(kpis, funnel, feature_usage, device_breakdown),
        "generatedAt": datetime.utcnow().isoformat(),
    }


def persist_event(db: Session, user_id: int | None, payload) -> ProductAnalyticsEvent:
    import json

    event = ProductAnalyticsEvent(
        user_id=user_id,
        session_id=payload.session_id.strip(),
        event_name=payload.event_name.strip(),
        feature=payload.feature.strip() or "general",
        funnel_name=payload.funnel_name.strip() if payload.funnel_name else None,
        funnel_step=payload.funnel_step.strip() if payload.funnel_step else None,
        device=payload.device,
        path=payload.path.strip(),
        duration_seconds=payload.duration_seconds,
        properties_json=json.dumps(payload.properties),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

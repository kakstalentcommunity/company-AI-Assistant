from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    path: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_security_events_severity_created", "severity", "created_at"),
        Index("ix_security_events_type_created", "event_type", "created_at"),
        Index("ix_security_events_ip_created", "ip_address", "created_at"),
    )

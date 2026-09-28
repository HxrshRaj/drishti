from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Base(DeclarativeBase):
    pass


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    operator_goal: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="planned")  # planned|running|awaiting_approval|completed|failed
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    findings: Mapped[list[Finding]] = relationship(back_populates="mission")
    approvals: Mapped[list[Approval]] = relationship(back_populates="mission")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    waypoint_id: Mapped[str] = mapped_column(String(32))
    image_file: Mapped[str] = mapped_column(String(256))
    finding_type: Mapped[str] = mapped_column(String(64))
    location_description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    verifier_outcome: Mapped[str] = mapped_column(String(32), default="unverified")  # agree|disagree|uncertain|unverified
    status: Mapped[str] = mapped_column(String(32), default="unresolved")  # unresolved|resolved
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    mission: Mapped[Mission] = relationship(back_populates="findings")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    action_description: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(16))  # low|medium|high
    proposing_agent: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected|modified
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    mission: Mapped[Mission] = relationship(back_populates="approvals")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    mission_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceRegistry(Base):
    __tablename__ = "source_registry"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    organization: Mapped[str] = mapped_column(String)
    product_family: Mapped[str] = mapped_column(String)
    base_url: Mapped[str] = mapped_column(String)
    allowed_hosts: Mapped[str] = mapped_column(Text)
    entitlements_json: Mapped[str] = mapped_column(Text)
    credential_ref: Mapped[str] = mapped_column(String)
    permission: Mapped[str] = mapped_column(String, default="read_only")
    expected_artifacts: Mapped[str] = mapped_column(Text)
    preferred_sop_id: Mapped[str | None] = mapped_column(String, nullable=True)
    allowed_operations_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[str] = mapped_column(Text, default="")


class SourceObligation(Base):
    __tablename__ = "source_obligation"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    cadence: Mapped[str] = mapped_column(String)
    expected_artifact: Mapped[str] = mapped_column(String)
    period: Mapped[str] = mapped_column(String)


class RawArtifact(Base):
    __tablename__ = "raw_artifact"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime)
    retrieval_method: Mapped[str] = mapped_column(String)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")


class SourceAssertion(Base):
    __tablename__ = "source_assertion"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String, ForeignKey("raw_artifact.id"))
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_type: Mapped[str] = mapped_column(String)
    subject_id: Mapped[str] = mapped_column(String)
    field: Mapped[str] = mapped_column(String)
    value_json: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    authority: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    notes: Mapped[str] = mapped_column(Text, default="")


class FinancialEvent(Base):
    __tablename__ = "financial_event"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String, default="USD")
    transaction_date: Mapped[str] = mapped_column(String)
    posting_date: Mapped[str] = mapped_column(String)
    financial_period: Mapped[str] = mapped_column(String)
    statement_id: Mapped[str | None] = mapped_column(String, nullable=True)


class EvidenceLink(Base):
    __tablename__ = "evidence_link"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    explanation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_key: Mapped[str] = mapped_column(String)
    artifact_id: Mapped[str | None] = mapped_column(String, nullable=True)
    assertion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Investigation(Base):
    __tablename__ = "investigation"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    explanation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pause_reason: Mapped[str] = mapped_column(Text, default="")


class InvestigationEvent(Base):
    __tablename__ = "investigation_event"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, default="orchestrator")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Conflict(Base):
    __tablename__ = "conflict"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    subject_id: Mapped[str] = mapped_column(String)
    assertion_ids_json: Mapped[str] = mapped_column(Text)
    materiality_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="open")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    likely_interpretation: Mapped[str] = mapped_column(Text, default="")
    remaining_uncertainty: Mapped[str] = mapped_column(Text, default="")
    sources_attempted_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class HumanResolution(Base):
    __tablename__ = "human_resolution"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conflict_id: Mapped[str] = mapped_column(String)
    investigation_id: Mapped[str] = mapped_column(String)
    decision: Mapped[str] = mapped_column(String)
    chosen_assertion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String)
    effective_at: Mapped[datetime] = mapped_column(DateTime)
    assertion_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Escalation(Base):
    __tablename__ = "escalation"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String)
    conflict_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    assertion_ids_json: Mapped[str] = mapped_column(Text)
    packet_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open")
    recommended_action: Mapped[str] = mapped_column(Text)
    materiality_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Explanation(Base):
    __tablename__ = "explanation"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String)
    headline: Mapped[str] = mapped_column(Text)
    narrative: Mapped[str] = mapped_column(Text)
    body_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)


class Sop(Base):
    __tablename__ = "sop"

    sop_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String)
    goal_type: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    parameters_json: Mapped[str] = mapped_column(Text)
    steps_json: Mapped[str] = mapped_column(Text)
    verification_json: Mapped[str] = mapped_column(Text)
    learned_hints_json: Mapped[str] = mapped_column(Text)
    created_from_run_id: Mapped[str | None] = mapped_column(String, nullable=True)


class SopRun(Base):
    __tablename__ = "sop_run"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sop_id: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    investigation_id: Mapped[str] = mapped_column(String)
    action_trace_json: Mapped[str] = mapped_column(Text)
    checks_json: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String)
    proposed_patch_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class CapabilityCache(Base):
    __tablename__ = "capability_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_name: Mapped[str] = mapped_column(String, index=True)
    query: Mapped[str] = mapped_column(Text)
    live: Mapped[bool] = mapped_column(Boolean)
    result_json: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime)

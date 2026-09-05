from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cashe.config import settings
from cashe.ids import iso, new_id, utcnow
from cashe.models import (
    CapabilityCache,
    Conflict,
    Escalation,
    EvidenceLink,
    Explanation,
    HumanResolution,
    Investigation,
    InvestigationEvent,
    RawArtifact,
    Sop,
    SopRun,
    SourceAssertion,
    SourceRegistry,
)


def _dump(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def persist_artifact(
    db: Session,
    *,
    source_id: str,
    media_type: str,
    payload: Any,
    retrieval_method: str,
    run_id: str | None,
    summary: str = "",
) -> RawArtifact:
    encoded = _dump(payload).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    artifact_id = new_id("art")
    path = settings.artifact_dir / f"{artifact_id}.json"
    with path.open("xb") as stream:
        stream.write(encoded)
    row = RawArtifact(
        id=artifact_id,
        source_id=source_id,
        media_type=media_type,
        content_hash=digest,
        storage_path=str(path),
        retrieved_at=utcnow(),
        retrieval_method=retrieval_method,
        run_id=run_id,
        summary=summary,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def persist_capture(db: Session, *, source_id: str, media_type: str, content: bytes,
                    run_id: str, summary: str = "") -> RawArtifact:
    extensions = {"image/png": ".png", "application/json": ".json"}
    if media_type not in extensions:
        raise ValueError("unsupported_capture_media_type")
    artifact_id = new_id("art")
    path = settings.artifact_dir / (artifact_id + extensions[media_type])
    with path.open("xb") as stream:
        stream.write(content)
    row = RawArtifact(id=artifact_id, source_id=source_id, media_type=media_type,
                      content_hash=hashlib.sha256(content).hexdigest(), storage_path=str(path),
                      retrieved_at=utcnow(), retrieval_method="browser", run_id=run_id, summary=summary)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def persist_assertion(
    db: Session,
    *,
    artifact_id: str,
    run_id: str | None,
    subject_type: str,
    subject_id: str,
    field: str,
    value: Any,
    authority: str,
    confidence: str,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    notes: str = "",
) -> SourceAssertion:
    row = SourceAssertion(
        id=new_id("ast"),
        artifact_id=artifact_id,
        run_id=run_id,
        subject_type=subject_type,
        subject_id=subject_id,
        field=field,
        value_json=_dump(value),
        valid_from=valid_from,
        valid_to=valid_to,
        observed_at=utcnow(),
        authority=authority,
        confidence=confidence,
        status="active",
        notes=notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def read_artifact_payload(artifact: RawArtifact) -> Any:
    return json.loads(settings.artifact_dir.joinpath(f"{artifact.id}.json").read_text())


def assertion_dict(row: SourceAssertion) -> dict:
    return {
        "id": row.id,
        "artifact_id": row.artifact_id,
        "run_id": row.run_id,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "field": row.field,
        "value": json.loads(row.value_json),
        "valid_from": iso(row.valid_from) if row.valid_from else None,
        "valid_to": iso(row.valid_to) if row.valid_to else None,
        "observed_at": iso(row.observed_at),
        "superseded_at": iso(row.superseded_at) if row.superseded_at else None,
        "authority": row.authority,
        "confidence": row.confidence,
        "status": row.status,
        "notes": row.notes,
    }


def source_dict(row: SourceRegistry) -> dict:
    return {
        "source_id": row.source_id,
        "organization": row.organization,
        "product_family": row.product_family,
        "base_url": row.base_url,
        "allowed_hosts": json.loads(row.allowed_hosts),
        "entitlements": json.loads(row.entitlements_json),
        "credential_ref": row.credential_ref,
        "permission": row.permission,
        "expected_artifacts": json.loads(row.expected_artifacts),
        "preferred_sop_id": row.preferred_sop_id,
        "allowed_operations": json.loads(row.allowed_operations_json),
        "notes": row.notes,
    }


def emit_event(
    db: Session,
    investigation_id: str,
    event_type: str,
    payload: Any,
    actor: str = "orchestrator",
) -> InvestigationEvent:
    last = db.scalar(
        select(InvestigationEvent.seq)
        .where(InvestigationEvent.investigation_id == investigation_id)
        .order_by(InvestigationEvent.seq.desc())
        .limit(1)
    )
    seq = (last or 0) + 1
    row = InvestigationEvent(
        id=new_id("evt"),
        investigation_id=investigation_id,
        seq=seq,
        event_type=event_type,
        actor=actor,
        payload_json=_dump(payload),
        created_at=utcnow(),
    )
    db.add(row)
    inv = db.get(Investigation, investigation_id)
    if inv:
        inv.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row


def as_of_assertions(db: Session, at: datetime) -> list[dict]:
    rows = db.scalars(select(SourceAssertion).order_by(SourceAssertion.observed_at)).all()
    out = []
    for row in rows:
        observed = row.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if observed > at:
            continue
        superseded = row.superseded_at
        if superseded is not None:
            if superseded.tzinfo is None:
                superseded = superseded.replace(tzinfo=timezone.utc)
            if superseded <= at:
                continue
        out.append(assertion_dict(row))
    return out


def current_assertions(db: Session) -> list[dict]:
    rows = db.scalars(
        select(SourceAssertion)
        .where(SourceAssertion.status == "active", SourceAssertion.superseded_at.is_(None))
        .order_by(SourceAssertion.observed_at.desc())
    ).all()
    return [assertion_dict(r) for r in rows]


def run_evidence(db: Session, run_id: str) -> dict:
    artifacts = db.scalars(select(RawArtifact).where(RawArtifact.run_id == run_id)).all()
    assertions = db.scalars(select(SourceAssertion).where(SourceAssertion.run_id == run_id)).all()
    conflicts = db.scalars(select(Conflict).where(Conflict.investigation_id == run_id)).all()
    escalations = db.scalars(select(Escalation).where(Escalation.investigation_id == run_id)).all()
    resolutions = db.scalars(select(HumanResolution).where(HumanResolution.investigation_id == run_id)).all()
    return {
        "artifacts": [
            {
                "id": a.id,
                "source_id": a.source_id,
                "media_type": a.media_type,
                "content_hash": a.content_hash,
                "retrieval_method": a.retrieval_method,
                "retrieved_at": iso(a.retrieved_at),
                "summary": a.summary,
            }
            for a in artifacts
        ],
        "assertions": [assertion_dict(a) for a in assertions],
        "conflicts": [
            {
                "id": c.id,
                "title": c.title,
                "subject_id": c.subject_id,
                "assertion_ids": json.loads(c.assertion_ids_json),
                "materiality_cents": c.materiality_cents,
                "status": c.status,
                "likely_interpretation": c.likely_interpretation,
                "remaining_uncertainty": c.remaining_uncertainty,
                "sources_attempted": json.loads(c.sources_attempted_json),
            }
            for c in conflicts
        ],
        "escalations": [
            {
                "id": e.id,
                "title": e.title,
                "kind": e.kind,
                "status": e.status,
                "materiality_cents": e.materiality_cents,
                "recommended_action": e.recommended_action,
            }
            for e in escalations
        ],
        "resolutions": [
            {
                "id": r.id,
                "conflict_id": r.conflict_id,
                "decision": r.decision,
                "chosen_assertion_id": r.chosen_assertion_id,
                "rationale": r.rationale,
                "reviewer": r.reviewer,
                "effective_at": iso(r.effective_at),
            }
            for r in resolutions
        ],
    }


def cache_capability(db: Session, source_name: str, query: str, live: bool, result: Any) -> CapabilityCache:
    row = CapabilityCache(
        id=new_id("cap"),
        source_name=source_name,
        query=query,
        live=live,
        result_json=_dump(result),
        retrieved_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

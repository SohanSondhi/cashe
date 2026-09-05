from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from cashe.db import session
from cashe.fixtures.statements import STATEMENTS, sequential_variance, statement_with_recon
from cashe.ids import new_id, utcnow
from cashe.models import Conflict, Escalation, EvidenceLink, Explanation, Investigation, Sop, SopRun, SourceRegistry
from cashe.research import tavily as tavily_research
from cashe.sources import accounting, bluepeak, procureflow
from cashe.store import (
    assertion_dict,
    cache_capability,
    emit_event,
    persist_artifact,
    persist_assertion,
    run_evidence,
    source_dict,
)
from cashe.voice.place_call import place_voice_call


def _schema(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


TOOL_SCHEMAS: dict[str, dict] = {
    "load_bank_statement": _schema(
        "load_bank_statement",
        "Load a hard-coded Northstar bank statement for a period (YYYY-MM). Bank is authoritative for settled cash only.",
        {"period": {"type": "string", "description": "Period such as 2026-08 or 2026-09"}},
        ["period"],
    ),
    "list_source_registry": _schema(
        "list_source_registry",
        "List configured sources, entitlements, and allowed operations for this customer.",
        {},
    ),
    "get_source": _schema(
        "get_source",
        "Get one source registry entry. source_id is kebab-case (example: novaworks-procureflow). Organization names are accepted and resolved.",
        {"source_id": {"type": "string"}},
        ["source_id"],
    ),
    "research_source_capabilities": _schema(
        "research_source_capabilities",
        "Tavily-backed advisory research on how a product is usually accessed. Not financial evidence. Combine with local entitlements.",
        {
            "source_name": {"type": "string"},
            "required_fact": {"type": "string"},
        },
        ["source_name", "required_fact"],
    ),
    "query_accounting_mcp": _schema(
        "query_accounting_mcp",
        "Call a read-only tool on the Cashe accounting MCP server.",
        {
            "tool": {
                "type": "string",
                "enum": ["list_open_invoices", "get_invoice", "get_customer", "get_expected_receipts"],
            },
            "arguments": {"type": "object"},
        },
        ["tool"],
    ),
    "query_source_api": _schema(
        "query_source_api",
        "Call a registered read-only REST operation on an API-entitled source.",
        {
            "source_id": {"type": "string"},
            "operation": {"type": "string"},
            "parameters": {"type": "object"},
        },
        ["source_id", "operation"],
    ),
    "run_bounded_browser": _schema(
        "run_bounded_browser",
        "Run a bounded read-only browser investigation against an allowlisted portal. Live agent is stubbed; portal evidence is still returned.",
        {
            "source_id": {"type": "string"},
            "goal": {"type": "string"},
            "sop_id": {"type": "string"},
            "step_budget": {"type": "integer"},
            "required_checks": {"type": "array", "items": {"type": "string"}},
            "invoice_number": {"type": "string"},
        },
        ["source_id", "goal"],
    ),
    "place_voice_call": _schema(
        "place_voice_call",
        "Place an outbound read-only voice call. Pass the purpose in objective. When the call ends, the full transcript is returned. Authority is COMMUNICATION / provisional.",
        {
            "source_id": {"type": "string"},
            "objective": {"type": "string"},
            "allowed_questions": {"type": "array", "items": {"type": "string"}},
            "turn_budget": {"type": "integer"},
        },
        ["source_id", "objective"],
    ),
    "get_sop": _schema(
        "get_sop",
        "Load a browser SOP by id. SOP memory is browser-only.",
        {"sop_id": {"type": "string"}},
        ["sop_id"],
    ),
    "list_run_evidence": _schema(
        "list_run_evidence",
        "List artifacts, assertions, conflicts, escalations, and human resolutions for this investigation.",
        {},
    ),
    "list_conflicts": _schema(
        "list_conflicts",
        "List open and resolved conflicts for this investigation.",
        {},
    ),
    "create_escalation": _schema(
        "create_escalation",
        "Create a human adjudication packet after authorized evidence paths are exhausted. Use for conflicts and low-authority claims.",
        {
            "title": {"type": "string"},
            "kind": {"type": "string", "description": "conflict or provisional_claim"},
            "subject_id": {"type": "string"},
            "assertion_ids": {"type": "array", "items": {"type": "string"}},
            "recommended_action": {"type": "string"},
            "materiality_cents": {"type": "integer"},
            "likely_interpretation": {"type": "string"},
            "remaining_uncertainty": {"type": "string"},
            "sources_attempted": {"type": "array", "items": {"type": "string"}},
        },
        ["title", "assertion_ids", "recommended_action", "materiality_cents"],
    ),
    "synthesize_explanation": _schema(
        "synthesize_explanation",
        "Store the evidence-backed cash-variance explanation with claim-level citations.",
        {
            "headline": {"type": "string"},
            "narrative": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "text": {"type": "string"},
                        "confidence": {"type": "string"},
                        "assertion_ids": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "open_conflicts": {"type": "array", "items": {"type": "string"}},
            "unknowns": {"type": "array", "items": {"type": "string"}},
            "drivers": {"type": "array"},
        },
        ["headline", "narrative", "claims"],
    ),
    "pause_for_human": _schema(
        "pause_for_human",
        "Pause the investigation until a human resolves open escalations.",
        {"reason": {"type": "string"}},
        ["reason"],
    ),
    "spawn_subagent": _schema(
        "spawn_subagent",
        "Create a specialized subagent with a narrow tool set. You choose the role, goal, and rationale. The runtime does not pick the source method for you.",
        {
            "role": {
                "type": "string",
                "enum": ["mcp", "api", "browser", "voice"],
            },
            "goal": {"type": "string"},
            "rationale": {
                "type": "string",
                "description": "Why this subagent and method, given entitlements, research, and remaining questions.",
            },
            "context": {"type": "string"},
        },
        ["role", "goal", "rationale"],
    ),
}


def schemas_for(names: list[str]) -> list[dict]:
    return [TOOL_SCHEMAS[n] for n in names if n in TOOL_SCHEMAS]


def _normalize(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def resolve_source(db: Session, source_id: str) -> SourceRegistry | None:
    row = db.get(SourceRegistry, source_id)
    if row:
        return row
    needle = _normalize(source_id)
    if not needle:
        return None
    for candidate in db.scalars(select(SourceRegistry)).all():
        sid = _normalize(candidate.source_id)
        org = _normalize(candidate.organization)
        family = _normalize(candidate.product_family)
        if needle in {sid, org, family}:
            return candidate
        if sid and (sid in needle or needle in sid):
            return candidate
        stem = _normalize((candidate.organization or "").split()[0])
        if stem and len(stem) >= 6 and stem in needle:
            return candidate
    return None


def _get_source(db: Session, source_id: str) -> SourceRegistry | None:
    return resolve_source(db, source_id)


def tool_load_bank_statement(db: Session, run_id: str, period: str) -> dict:
    if period not in STATEMENTS:
        return {"error": "unknown_period", "period": period, "available": list(STATEMENTS)}
    payload = statement_with_recon(period)
    art = persist_artifact(
        db,
        source_id="northstar-bank",
        media_type="application/json",
        payload=payload,
        retrieval_method="bank_statement_fixture",
        run_id=run_id,
        summary=f"Northstar statement {period}",
    )
    persist_assertion(
        db,
        artifact_id=art.id,
        run_id=run_id,
        subject_type="account",
        subject_id=payload["account_id"],
        field="closing_booked_balance_cents",
        value=payload["closing_booked_balance_cents"],
        authority="SETTLEMENT",
        confidence="verified",
        valid_from=datetime.fromisoformat(payload["period_end"] + "T00:00:00+00:00"),
        notes=f"period {period}",
    )
    persist_assertion(
        db,
        artifact_id=art.id,
        run_id=run_id,
        subject_type="account",
        subject_id=payload["account_id"],
        field="net_cash_cents",
        value=payload["reconciliation"]["net_cash_cents"],
        authority="SETTLEMENT",
        confidence="verified",
        notes=f"period {period}",
    )
    variance = sequential_variance() if period == "2026-09" else None
    return {
        "artifact_id": art.id,
        "statement": payload,
        "reconciliation": payload["reconciliation"],
        "sequential_variance": variance,
        "authority": "SETTLEMENT",
        "note": "Bank is authoritative for settled cash only.",
    }


def tool_list_source_registry(db: Session, run_id: str) -> dict:
    rows = db.scalars(select(SourceRegistry)).all()
    return {"sources": [source_dict(r) for r in rows]}


def tool_get_source(db: Session, run_id: str, source_id: str) -> dict:
    row = _get_source(db, source_id)
    if not row:
        rows = db.scalars(select(SourceRegistry)).all()
        return {
            "error": "unknown_source",
            "source_id": source_id,
            "hint": "Use an exact source_id from list_source_registry.",
            "known_source_ids": [r.source_id for r in rows],
        }
    return source_dict(row)


def tool_research(db: Session, run_id: str, source_name: str, required_fact: str) -> dict:
    result = tavily_research.research(source_name, required_fact)
    live = result.get("cache_status") == "live"
    art = persist_artifact(
        db,
        source_id="tavily",
        media_type="application/json",
        payload=result,
        retrieval_method="tavily_live" if live else "tavily_cache",
        run_id=run_id,
        summary=f"Capability research for {source_name}",
    )
    cache_capability(db, source_name, result.get("query", required_fact), live, result)
    return {
        "artifact_id": art.id,
        "advisory_only": True,
        "not_financial_evidence": True,
        **result,
    }


def tool_query_mcp(db: Session, run_id: str, tool: str, arguments: dict | None = None) -> dict:
    payload = accounting.invoke(tool, arguments or {})
    art = persist_artifact(
        db,
        source_id="cashe-accounting-mcp",
        media_type="application/json",
        payload=payload,
        retrieval_method="mcp",
        run_id=run_id,
        summary=f"MCP {tool}",
    )
    assertions = []
    invoices = payload.get("invoices") or payload.get("receipts") or []
    if payload.get("invoice"):
        invoices = [payload["invoice"]]
    for inv in invoices:
        for field in ("status", "amount_cents", "legal_entity", "due_date", "customer"):
            if field in inv:
                ast = persist_assertion(
                    db,
                    artifact_id=art.id,
                    run_id=run_id,
                    subject_type="invoice",
                    subject_id=inv["invoice_number"],
                    field=field,
                    value=inv[field],
                    authority="BOOKS",
                    confidence="verified",
                )
                assertions.append(assertion_dict(ast))
    if "total_open_cents" in payload:
        ast = persist_assertion(
            db,
            artifact_id=art.id,
            run_id=run_id,
            subject_type="receivables",
            subject_id="CASH-US",
            field="total_open_cents",
            value=payload["total_open_cents"],
            authority="BOOKS",
            confidence="verified",
        )
        assertions.append(assertion_dict(ast))
    if "total_cents" in payload:
        ast = persist_assertion(
            db,
            artifact_id=art.id,
            run_id=run_id,
            subject_type="receivables",
            subject_id="CASH-US",
            field="expected_receipts_cents",
            value=payload["total_cents"],
            authority="BOOKS",
            confidence="verified",
        )
        assertions.append(assertion_dict(ast))
    return {"artifact_id": art.id, "result": payload, "assertions": assertions}


def tool_query_api(db: Session, run_id: str, source_id: str, operation: str, parameters: dict | None = None) -> dict:
    src = _get_source(db, source_id)
    if not src:
        return {"error": "unknown_source", "source_id": source_id}
    entitlements = json.loads(src.entitlements_json)
    if not entitlements.get("api"):
        return {
            "error": "api_not_entitled",
            "source_id": source_id,
            "entitlements": entitlements,
            "note": "General platform capability does not imply customer authorization.",
        }
    allowed = json.loads(src.allowed_operations_json)
    if operation not in allowed:
        return {"error": "operation_not_registered", "operation": operation, "allowed": allowed}
    if source_id != "novaworks-procureflow":
        return {"error": "no_api_adapter", "source_id": source_id}
    payload = procureflow.invoke(operation, parameters or {})
    art = persist_artifact(
        db,
        source_id=source_id,
        media_type="application/json",
        payload=payload,
        retrieval_method="api",
        run_id=run_id,
        summary=f"API {source_id} {operation}",
    )
    assertions = []
    subject = payload.get("invoice_number") or (parameters or {}).get("invoice_number") or source_id
    for field in (
        "status",
        "delay_days",
        "blocking_reason",
        "first_attempted_submission",
        "successful_submission",
        "po_number",
        "amount_cents",
    ):
        if field in payload:
            ast = persist_assertion(
                db,
                artifact_id=art.id,
                run_id=run_id,
                subject_type="invoice",
                subject_id=subject,
                field=field,
                value=payload[field],
                authority="WORKFLOW",
                confidence="verified",
            )
            assertions.append(assertion_dict(ast))
    return {"artifact_id": art.id, "result": payload, "assertions": assertions}


def tool_browser(
    db: Session,
    run_id: str,
    source_id: str,
    goal: str,
    sop_id: str | None = None,
    step_budget: int = 20,
    required_checks: list[str] | None = None,
    invoice_number: str = "INV-BP-2088",
) -> dict:
    src = _get_source(db, source_id)
    if not src:
        return {"error": "unknown_source", "source_id": source_id}
    entitlements = json.loads(src.entitlements_json)
    if not entitlements.get("browser"):
        return {"error": "browser_not_entitled", "source_id": source_id, "entitlements": entitlements}
    hosts = json.loads(src.allowed_hosts)
    if "localhost" not in hosts:
        return {"error": "host_not_allowlisted", "allowed_hosts": hosts}
    sop = None
    if sop_id:
        row = db.get(Sop, sop_id)
        if row:
            sop = {
                "sop_id": row.sop_id,
                "version": row.version,
                "status": row.status,
                "steps": json.loads(row.steps_json),
                "verification": json.loads(row.verification_json),
            }
    payload = bluepeak.mock_browser_run(invoice_number, sop, step_budget)
    art = persist_artifact(
        db,
        source_id=source_id,
        media_type="application/json",
        payload=payload,
        retrieval_method="browser_mocked",
        run_id=run_id,
        summary=f"Browser capture {invoice_number}",
    )
    extracted = payload.get("extracted") or {}
    assertions = []
    mapping = {
        "status": extracted.get("status"),
        "legal_entity": extracted.get("legal_entity"),
        "rejection_count": extracted.get("rejection_count"),
        "dispute_reason": extracted.get("dispute_reason"),
        "amount_cents": extracted.get("amount_cents"),
    }
    for field, value in mapping.items():
        if value is not None:
            confidence = "verified" if payload.get("checks_passed") else "provisional"
            ast = persist_assertion(
                db,
                artifact_id=art.id,
                run_id=run_id,
                subject_type="invoice",
                subject_id=invoice_number,
                field=field,
                value=value,
                authority="WORKFLOW",
                confidence=confidence,
                notes="Portal workflow state. Not bank settlement.",
            )
            assertions.append(assertion_dict(ast))
    db.add(
        SopRun(
            id=new_id("spr"),
            sop_id=sop_id or "",
            source_id=source_id,
            investigation_id=run_id,
            action_trace_json=json.dumps(payload.get("action_trace") or []),
            checks_json=json.dumps(payload.get("checks") or {}),
            outcome="verified" if payload.get("checks_passed") else "failed",
            proposed_patch_json=json.dumps(payload.get("proposed_sop_patch") or {}),
            created_at=utcnow(),
        )
    )
    db.commit()
    return {"artifact_id": art.id, "result": payload, "assertions": assertions, "sop_used": sop_id}


def tool_voice(
    db: Session,
    run_id: str,
    source_id: str,
    objective: str,
    allowed_questions: list[str] | None = None,
    turn_budget: int = 8,
) -> dict:
    src = _get_source(db, source_id)
    if not src:
        return {"error": "unknown_source", "source_id": source_id}
    entitlements = json.loads(src.entitlements_json)
    if not entitlements.get("voice"):
        return {"error": "voice_not_entitled", "source_id": source_id, "entitlements": entitlements}
    payload = place_voice_call(
        objective,
        allowed_questions or [],
        turn_budget,
        source_id=src.source_id,
    )
    transcript = payload.get("transcript") or []
    if payload.get("mocked"):
        retrieval_method = "voice_mocked"
    elif payload.get("live"):
        retrieval_method = "voice_live"
    else:
        retrieval_method = "voice"
    art = persist_artifact(
        db,
        source_id=source_id,
        media_type="application/json",
        payload=payload,
        retrieval_method=retrieval_method,
        run_id=run_id,
        summary=f"Voice transcript ({len(transcript)} turns)",
    )
    assertions = []
    ast = persist_assertion(
        db,
        artifact_id=art.id,
        run_id=run_id,
        subject_type="call",
        subject_id=src.source_id,
        field="transcript",
        value=transcript,
        authority="COMMUNICATION",
        confidence="provisional",
        notes="Full call transcript. Requires documentary corroboration or human acceptance.",
    )
    assertions.append(assertion_dict(ast))
    extracted = payload.get("extracted") or {}
    for field, value in extracted.items():
        if value is None:
            continue
        ast = persist_assertion(
            db,
            artifact_id=art.id,
            run_id=run_id,
            subject_type="invoice",
            subject_id=str(extracted.get("invoice_number") or src.source_id),
            field=field,
            value=value,
            authority="COMMUNICATION",
            confidence="provisional",
            notes="Voice claim. Requires documentary corroboration or human acceptance.",
        )
        assertions.append(assertion_dict(ast))
    return {
        "artifact_id": art.id,
        "purpose": objective,
        "transcript": transcript,
        "result": payload,
        "assertions": assertions,
        "note": "Full transcript is in transcript. Extract claims from it; do not invent lines.",
    }


def tool_get_sop(db: Session, run_id: str, sop_id: str) -> dict:
    row = db.get(Sop, sop_id)
    if not row:
        return {"error": "unknown_sop", "sop_id": sop_id}
    return {
        "sop_id": row.sop_id,
        "source_id": row.source_id,
        "goal_type": row.goal_type,
        "version": row.version,
        "status": row.status,
        "parameters": json.loads(row.parameters_json),
        "steps": json.loads(row.steps_json),
        "verification": json.loads(row.verification_json),
        "learned_hints": json.loads(row.learned_hints_json),
    }


def tool_list_run_evidence(db: Session, run_id: str) -> dict:
    return run_evidence(db, run_id)


def tool_list_conflicts(db: Session, run_id: str) -> dict:
    rows = db.scalars(select(Conflict).where(Conflict.investigation_id == run_id)).all()
    return {
        "conflicts": [
            {
                "id": c.id,
                "title": c.title,
                "subject_id": c.subject_id,
                "assertion_ids": json.loads(c.assertion_ids_json),
                "status": c.status,
                "materiality_cents": c.materiality_cents,
                "likely_interpretation": c.likely_interpretation,
                "remaining_uncertainty": c.remaining_uncertainty,
                "sources_attempted": json.loads(c.sources_attempted_json),
            }
            for c in rows
        ]
    }


def tool_create_escalation(
    db: Session,
    run_id: str,
    title: str,
    assertion_ids: list[str],
    recommended_action: str,
    materiality_cents: int,
    kind: str = "conflict",
    subject_id: str = "",
    likely_interpretation: str = "",
    remaining_uncertainty: str = "",
    sources_attempted: list[str] | None = None,
) -> dict:
    conflict = Conflict(
        id=new_id("cnf"),
        investigation_id=run_id,
        title=title,
        subject_id=subject_id or ",".join(assertion_ids[:1]),
        assertion_ids_json=json.dumps(assertion_ids),
        materiality_cents=materiality_cents,
        status="open",
        recommended_action=recommended_action,
        likely_interpretation=likely_interpretation,
        remaining_uncertainty=remaining_uncertainty,
        sources_attempted_json=json.dumps(sources_attempted or []),
        created_at=utcnow(),
    )
    db.add(conflict)
    packet = {
        "title": title,
        "kind": kind,
        "assertion_ids": assertion_ids,
        "evidence": run_evidence(db, run_id),
        "likely_interpretation": likely_interpretation,
        "remaining_uncertainty": remaining_uncertainty,
        "recommended_action": recommended_action,
        "sources_attempted": sources_attempted or [],
        "available_decisions": [
            "Approve provisionally",
            "Choose an assertion",
            "Request more evidence",
            "Correct the entity mapping",
            "Reject the proposed interpretation",
        ],
    }
    esc = Escalation(
        id=new_id("esc"),
        investigation_id=run_id,
        conflict_id=conflict.id,
        title=title,
        kind=kind,
        assertion_ids_json=json.dumps(assertion_ids),
        packet_json=json.dumps(packet, default=str),
        status="open",
        recommended_action=recommended_action,
        materiality_cents=materiality_cents,
        created_at=utcnow(),
    )
    db.add(esc)
    db.commit()
    emit_event(
        db,
        run_id,
        "escalation",
        {"escalation_id": esc.id, "conflict_id": conflict.id, "title": title, "kind": kind},
        actor="orchestrator",
    )
    return {"escalation_id": esc.id, "conflict_id": conflict.id, "packet": packet}


def tool_synthesize_explanation(
    db: Session,
    run_id: str,
    headline: str,
    narrative: str,
    claims: list[dict],
    open_conflicts: list[str] | None = None,
    unknowns: list[str] | None = None,
    drivers: list | None = None,
) -> dict:
    body = {
        "headline": headline,
        "narrative": narrative,
        "claims": claims,
        "open_conflicts": open_conflicts or [],
        "unknowns": unknowns or [],
        "drivers": drivers or [],
    }
    expl = Explanation(
        id=new_id("exp"),
        investigation_id=run_id,
        headline=headline,
        narrative=narrative,
        body_json=json.dumps(body, default=str),
        created_at=utcnow(),
        accepted=not bool(open_conflicts),
    )
    db.add(expl)
    inv = db.get(Investigation, run_id)
    if inv:
        inv.explanation_id = expl.id
        if not open_conflicts:
            inv.status = "completed"
            inv.completed_at = utcnow()
    db.commit()
    for claim in claims:
        for ast_id in claim.get("assertion_ids") or []:
            db.add(
                EvidenceLink(
                    id=new_id("lnk"),
                    explanation_id=expl.id,
                    claim_key=claim.get("key", ""),
                    assertion_id=ast_id,
                )
            )
    db.commit()
    emit_event(db, run_id, "explanation", {"explanation_id": expl.id, "headline": headline}, actor="orchestrator")
    return {"explanation_id": expl.id, "explanation": body}


def tool_pause(db: Session, run_id: str, reason: str) -> dict:
    inv = db.get(Investigation, run_id)
    if inv:
        inv.status = "awaiting_human"
        inv.pause_reason = reason
        inv.updated_at = utcnow()
        db.commit()
    emit_event(db, run_id, "pause", {"reason": reason})
    return {"status": "awaiting_human", "reason": reason}


HANDLERS: dict[str, Callable] = {
    "load_bank_statement": tool_load_bank_statement,
    "list_source_registry": tool_list_source_registry,
    "get_source": tool_get_source,
    "research_source_capabilities": tool_research,
    "query_accounting_mcp": tool_query_mcp,
    "query_source_api": tool_query_api,
    "run_bounded_browser": tool_browser,
    "place_voice_call": tool_voice,
    "get_sop": tool_get_sop,
    "list_run_evidence": tool_list_run_evidence,
    "list_conflicts": tool_list_conflicts,
    "create_escalation": tool_create_escalation,
    "synthesize_explanation": tool_synthesize_explanation,
    "pause_for_human": tool_pause,
}


ORCHESTRATOR_TOOL_NAMES = [
    "load_bank_statement",
    "list_source_registry",
    "get_source",
    "research_source_capabilities",
    "spawn_subagent",
    "list_run_evidence",
    "list_conflicts",
    "create_escalation",
    "pause_for_human",
    "synthesize_explanation",
]


def execute_tool(name: str, arguments: dict, run_id: str) -> dict:
    db = session()
    try:
        if name == "spawn_subagent":
            return {"error": "spawn_subagent_handled_by_loop"}
        handler = HANDLERS.get(name)
        if not handler:
            return {"error": "unknown_tool", "name": name}
        return handler(db, run_id, **arguments)
    except TypeError as exc:
        return {"error": "bad_arguments", "detail": str(exc), "arguments": arguments}
    except Exception as exc:  # noqa: BLE001
        return {"error": "tool_failed", "detail": str(exc)}
    finally:
        db.close()

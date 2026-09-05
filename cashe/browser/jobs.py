"""Explicit browser test jobs writing to the same evidence store as the operator UI."""

import json

from sqlalchemy import select

from cashe.db import session
from cashe.ids import utcnow
from cashe.models import Investigation, InvestigationEvent, RawArtifact, SopRun
from cashe.store import emit_event, read_artifact_payload, run_evidence


def run_browser_test(run_id: str, source_id: str, invoice_number: str, step_budget: int = 20):
    # This is an explicitly requested browser test, not an automatic source router.
    # Actual acquisition/model/read actions use the existing PRISM callback wrapper.
    from cashe.orchestrator.tools import tool_browser, tool_query_mcp

    with session() as db:
        inv = db.get(Investigation, run_id)
        if inv is None:
            return
        try:
            emit_event(db, run_id, "browser_test_started", {"source_id": source_id, "invoice_number": invoice_number}, actor="browser")
            tool_query_mcp(db, run_id, "get_invoice", {"invoice_number": invoice_number})
            result = tool_browser(db, run_id, source_id,
                                  goal=f"Retrieve status, amount, submitted legal entity, dispute reason and complete timeline for {invoice_number}",
                                  invoice_number=invoice_number, step_budget=step_budget)
            report = result.get("result", {})
            inv.status = "evidence_ready" if report.get("checks_passed") else "failed"
            inv.pause_reason = ("Portal evidence is ready. Financial conflicts still require investigation and review."
                                if report.get("checks_passed") else "; ".join(report.get("remaining_gaps") or [result.get("error", "browser_failed")]))
            emit_event(db, run_id, "browser_test_finished", {"status": inv.status, "artifact_id": result.get("artifact_id"),
                                                           "message": inv.pause_reason}, actor="browser")
        except Exception as exc:
            db.rollback()
            inv = db.get(Investigation, run_id)
            inv.status = "failed"
            inv.pause_reason = f"Browser test failed: {type(exc).__name__}"
            emit_event(db, run_id, "browser_test_finished", {"status": "failed", "message": inv.pause_reason}, actor="browser")
        inv.updated_at = utcnow()
        # Acquisition completion is not acceptance of a financial explanation.
        db.commit()


def evidence_for_ui(db, run_id: str) -> dict:
    data = run_evidence(db, run_id)
    for artifact in data["artifacts"]:
        artifact["url"] = f"/evidence/{artifact['id']}"
        artifact["content_url"] = f"/api/evidence/{artifact['id']}/content"
    runs = db.scalars(select(SopRun).where(SopRun.investigation_id == run_id).order_by(SopRun.created_at)).all()
    data["browser_runs"] = [{"id": run.id, "status": run.outcome, "sop_id": run.sop_id,
                             "checks": json.loads(run.checks_json),
                             "steps_used": len(json.loads(run.action_trace_json))} for run in runs]
    reports = []
    events = db.scalars(select(InvestigationEvent).where(
        InvestigationEvent.investigation_id == run_id, InvestigationEvent.event_type == "browser_completed"
    ).order_by(InvestigationEvent.seq)).all()
    for event in events:
        artifact_id = json.loads(event.payload_json).get("artifact_id")
        artifact = db.get(RawArtifact, artifact_id) if artifact_id else None
        if artifact and artifact.run_id == run_id:
            report = read_artifact_payload(artifact)
            reports.append({"artifact_id": artifact_id, "status": report["status"],
                            "checks": report["checks"], "remaining_gaps": report["remaining_gaps"],
                            "steps_used": report["steps_used"], "decision_mode": report["decision_mode"]})
    data["browser_reports"] = reports
    return data

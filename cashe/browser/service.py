"""Bridge browser evidence into SQLite and browser-only procedure memory."""

import json
from datetime import datetime

from sqlalchemy import func, select

from cashe.browser.contracts import BrowserTask
from cashe.browser.policy import load_profile
from cashe.browser.runner import run_browser
from cashe.ids import new_id, utcnow
from cashe.models import EvidenceLink, Sop, SopRun, SourceAssertion
from cashe.store import assertion_dict, emit_event, persist_artifact, persist_assertion, persist_capture, source_dict


def sop_dict(row: Sop) -> dict:
    return {"sop_id": row.sop_id, "source_id": row.source_id, "version": row.version,
            "status": row.status, "steps": json.loads(row.steps_json),
            "verification": json.loads(row.verification_json),
            "learned_hints": json.loads(row.learned_hints_json)}


def accounting_expectations(db, run_id: str, invoice_number: str) -> dict:
    rows = db.scalars(select(SourceAssertion).where(
        SourceAssertion.run_id == run_id, SourceAssertion.subject_id == invoice_number,
        SourceAssertion.subject_type == "invoice", SourceAssertion.authority == "BOOKS",
        SourceAssertion.confidence == "verified", SourceAssertion.status == "active",
    )).all()
    result = {"assertion_ids": [row.id for row in rows]}
    for field in ("customer", "amount_cents", "currency", "legal_entity"):
        values = {row.value_json for row in rows if row.field == field}
        if len(values) == 1:
            result[field] = json.loads(next(iter(values)))
    return result


def acquire(db, run_id: str, source, *, goal: str, invoice_number: str,
            sop_id=None, step_budget=20, required_checks=None, decider=None) -> dict:
    selected_sop = sop_id if sop_id is not None else source.preferred_sop_id
    row = db.get(Sop, selected_sop) if selected_sop else None
    if selected_sop and (not row or row.source_id != source.source_id or row.status != "approved"):
        return {"error": "approved_source_sop_required", "sop_id": selected_sop}
    try:
        task_args = dict(source_id=source.source_id, goal=goal, invoice_number=invoice_number,
                         step_budget=step_budget, expected=accounting_expectations(db, run_id, invoice_number))
        if required_checks is not None:
            task_args["required_checks"] = required_checks
        task = BrowserTask.model_validate(task_args)
        profile = load_profile(source.source_id)
    except ValueError as exc:
        return {"error": "invalid_browser_task_or_profile", "detail": str(exc)}

    def save(media_type, content, summary):
        return persist_capture(db, source_id=source.source_id, media_type=media_type,
                               content=content, run_id=run_id, summary=summary).id

    payload = run_browser(task, source_dict(source), profile, sop_dict(row) if row else None,
                          run_id=run_id, save_capture=save,
                          emit=lambda event: emit_event(db, run_id, "browser_capture", event, actor="browser"),
                          decider=decider)
    art = persist_artifact(db, source_id=source.source_id, media_type="application/json",
                           payload=payload, retrieval_method="browser", run_id=run_id,
                           summary=f"Browser {payload['status']}: {invoice_number}")
    observations = {o["id"]: o for o in payload["observations"]}
    assertions = []
    identity_ok = payload["checks"].get("invoice_number_matches") and payload["checks"].get("customer_matches")
    for field, citation in (payload.get("field_citations", {}) if identity_ok else {}).items():
        observation = observations[citation["observation_id"]]
        ast = persist_assertion(db, artifact_id=observation["artifact_id"], run_id=run_id,
                                subject_type="invoice", subject_id=invoice_number, field=field,
                                value=payload["extracted"][field], authority="WORKFLOW",
                                confidence="verified" if payload["checks_passed"] else "provisional",
                                notes=json.dumps({"quote": citation["quote"], "url": observation["url"],
                                                  "observation_id": observation["id"],
                                                  "scope": "Portal workflow; not settled cash or entity adjudication."}))
        db.add(EvidenceLink(id=new_id("evl"), claim_key=field, assertion_id=ast.id,
                            artifact_id=observation["screenshot_artifact_id"]))
        assertions.append(assertion_dict(ast))
    for event in (payload.get("extracted", {}).get("timeline", []) if identity_ok else []):
        observation = observations[event["observation_id"]]
        ast = persist_assertion(db, artifact_id=observation["artifact_id"], run_id=run_id,
                                subject_type="invoice", subject_id=invoice_number, field="timeline_event",
                                value=event["quote"], authority="WORKFLOW",
                                valid_from=datetime.fromisoformat(event["valid_from"]),
                                confidence="verified" if payload["checks_passed"] else "provisional")
        db.add(EvidenceLink(id=new_id("evl"), claim_key="timeline_event", assertion_id=ast.id,
                            artifact_id=observation["screenshot_artifact_id"]))
        assertions.append(assertion_dict(ast))

    sop_run_id = new_id("spr")
    patch = payload["proposed_sop_patch"]
    # A fully verified success can promote a new version (spec section 12).
    # Never mutate the prior procedure or promote failed/partial navigation.
    if payload["checks_passed"] and patch:
        hints = sorted(set((json.loads(row.learned_hints_json) if row else []) + patch["learned_hints"]))
        if not row or hints != sorted(json.loads(row.learned_hints_json)):
            version = (db.scalar(select(func.max(Sop.version)).where(Sop.source_id == source.source_id)) or 0) + 1
            revision_id = new_id("sop")
            db.add(Sop(sop_id=revision_id, source_id=source.source_id,
                       goal_type="retrieve_invoice_status", version=version, status="approved",
                       parameters_json=json.dumps(["invoice_number"]),
                       steps_json=json.dumps(patch["steps"]), verification_json=json.dumps(sorted(payload["checks"])),
                       learned_hints_json=json.dumps(hints), created_from_run_id=sop_run_id))
            patch.update(parent_sop_id=selected_sop, promoted_sop_id=revision_id,
                         promotion_reason="fully_verified_browser_success")
            source.preferred_sop_id = revision_id
    db.add(SopRun(id=sop_run_id, sop_id=selected_sop or "", source_id=source.source_id,
                  investigation_id=run_id, action_trace_json=json.dumps(payload["action_trace"]),
                  checks_json=json.dumps(payload["checks"]), outcome=payload["status"],
                  proposed_patch_json=json.dumps(patch), created_at=utcnow()))
    db.commit()
    emit_event(db, run_id, "browser_completed", {"status": payload["status"], "artifact_id": art.id,
                                                "steps_used": payload["steps_used"], "sop_run_id": sop_run_id}, actor="browser")
    result = {"artifact_id": art.id, "result": payload, "assertions": assertions,
              "sop_used": selected_sop, "sop_run_id": sop_run_id, "sop_update": patch}
    if not payload["checks_passed"]:
        result["error"] = "browser_" + payload["status"]
    return result

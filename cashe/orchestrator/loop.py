from __future__ import annotations

import json
from typing import Any

from cashe.config import settings
from cashe.db import session
from cashe.ids import new_id, utcnow
from sqlalchemy import select

from cashe.models import Escalation, HumanResolution, Investigation, SourceAssertion
from cashe.orchestrator.client import PrismClient, message_to_dict, parse_arguments
from cashe.orchestrator.prompts import ORCHESTRATOR_POLICY, ROLE_PROMPTS, ROLE_TOOLS
from cashe.orchestrator.tools import (
    ORCHESTRATOR_TOOL_NAMES,
    execute_tool,
    schemas_for,
)
from cashe.store import emit_event, persist_artifact, persist_assertion, run_evidence

_client: PrismClient | None = None


def client() -> PrismClient:
    global _client
    if _client is None:
        _client = PrismClient()
    return _client


def _dump(value: Any) -> str:
    return json.dumps(value, default=str)


def _messages_path(run_id: str):
    return settings.artifact_dir / f"{run_id}-messages.json"


def save_messages(run_id: str, messages: list[dict]) -> None:
    _messages_path(run_id).write_text(_dump(messages))


def load_messages(run_id: str) -> list[dict] | None:
    path = _messages_path(run_id)
    if path.exists():
        return json.loads(path.read_text())
    return None


def _compact_result(result: Any) -> str:
    text = _dump(result)
    if len(text) > 10_000:
        return text[:10_000] + '...[truncated]"'
    return text


def run_llm_loop(
    *,
    run_id: str,
    actor: str,
    system: str,
    user: str,
    tool_names: list[str],
    extra_messages: list[dict] | None = None,
    max_steps: int = 24,
    allow_spawn: bool = False,
) -> dict:
    db = session()
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    if extra_messages:
        messages.extend(extra_messages)
    messages.append({"role": "user", "content": user})
    tools = schemas_for(tool_names)
    paused = False
    completed = False
    last_text = ""

    try:
        for step in range(max_steps):
            emit_event(db, run_id, "llm_turn", {"actor": actor, "step": step}, actor=actor)
            db.close()
            db = session()
            response = client().chat(messages, tools=tools or None)
            choice = response.choices[0]
            message = choice.message
            messages.append(message_to_dict(message))
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                last_text = message.content or ""
                emit_event(db, run_id, "llm_message", {"actor": actor, "text": last_text[:4000]}, actor=actor)
                break

            for tc in tool_calls:
                name = tc.function.name
                args = parse_arguments(tc.function.arguments)
                emit_event(
                    db,
                    run_id,
                    "tool_call",
                    {"actor": actor, "tool": name, "arguments": args},
                    actor=actor,
                )
                if name == "spawn_subagent":
                    if not allow_spawn:
                        result = {"error": "subagents_cannot_spawn_subagents"}
                    else:
                        result = spawn_subagent(run_id, args)
                else:
                    result = execute_tool(name, args, run_id)
                emit_event(
                    db,
                    run_id,
                    "tool_result",
                    {
                        "actor": actor,
                        "tool": name,
                        "ok": "error" not in result,
                        "preview": _compact_result(result)[:2000],
                    },
                    actor=actor,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _compact_result(result),
                    }
                )
                if name == "pause_for_human":
                    paused = True
                if name == "synthesize_explanation" and result.get("explanation_id"):
                    if not result.get("explanation", {}).get("open_conflicts"):
                        completed = True

            save_messages(run_id, messages)
            if paused or completed:
                break
        else:
            emit_event(db, run_id, "step_budget_exhausted", {"actor": actor, "max_steps": max_steps}, actor=actor)
    except Exception as exc:  # noqa: BLE001
        emit_event(db, run_id, "llm_error", {"actor": actor, "error": str(exc)}, actor=actor)
        last_text = f"LLM error: {exc}"
        raise
    finally:
        save_messages(run_id, messages)
        db.close()

    return {"text": last_text, "paused": paused, "completed": completed, "messages": messages}


def spawn_subagent(run_id: str, args: dict) -> dict:
    role = args.get("role")
    goal = args.get("goal", "")
    rationale = args.get("rationale", "")
    context = args.get("context", "")
    if role not in ROLE_PROMPTS:
        return {"error": "unknown_role", "role": role, "known": list(ROLE_PROMPTS)}

    db = session()
    try:
        emit_event(
            db,
            run_id,
            "subagent_spawn",
            {"role": role, "goal": goal, "rationale": rationale},
            actor="orchestrator",
        )
    finally:
        db.close()

    user = (
        f"Investigation id: {run_id}\n"
        f"Goal: {goal}\n"
        f"Orchestrator rationale: {rationale}\n"
        f"Additional context:\n{context}\n"
        "Use your tools. Return a concise evidence report: what you learned, "
        "assertion IDs, remaining gaps, and whether another source should corroborate."
    )
    result = run_llm_loop(
        run_id=run_id,
        actor=f"subagent:{role}",
        system=ROLE_PROMPTS[role],
        user=user,
        tool_names=ROLE_TOOLS[role],
        max_steps=10,
        allow_spawn=False,
    )

    db = session()
    try:
        emit_event(
            db,
            run_id,
            "subagent_complete",
            {"role": role, "goal": goal, "rationale": rationale, "report": (result.get("text") or "")[:4000]},
            actor=f"subagent:{role}",
        )
        evidence = run_evidence(db, run_id)
    finally:
        db.close()

    return {
        "role": role,
        "goal": goal,
        "rationale": rationale,
        "report": result.get("text"),
        "assertion_ids": [a["id"] for a in evidence.get("assertions", [])][-20:],
        "artifact_ids": [a["id"] for a in evidence.get("artifacts", [])][-12:],
        "escalation_ids": [e["id"] for e in evidence.get("escalations", [])],
        "note": "Full payloads live in list_run_evidence. This report is the subagent's conclusion.",
    }


def start_investigation(question: str) -> str:
    db = session()
    inv = Investigation(
        id=new_id("inv"),
        question=question,
        status="running",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(inv)
    db.commit()
    run_id = inv.id
    emit_event(db, run_id, "started", {"question": question})
    db.close()
    return run_id


def continue_investigation(run_id: str, *, resume: bool = False) -> dict:
    db = session()
    inv = db.get(Investigation, run_id)
    if not inv:
        db.close()
        return {"error": "unknown_investigation"}
    inv.status = "running"
    inv.updated_at = utcnow()
    db.commit()
    question = inv.question
    db.close()

    extra = None
    user = (
        "Company: Cashe Software, Inc. Entity code CASH-US. "
        "Bank: Northstar Commercial Bank, Operating ••1842, USD.\n"
        f"Question: {question}\n\n"
        "Bank statements for 2026-08 and 2026-09 are available through load_bank_statement. "
        "Source access is described in list_source_registry. "
        "Research capabilities yourself with research_source_capabilities. "
        "Investigate by spawning mcp, api, browser, or voice subagents. "
        "Do not treat Tavily research as financial evidence."
    )
    if resume:
        prior = load_messages(run_id) or []
        extra = [m for m in prior if m.get("role") != "system"]
        db_ev = session()
        try:
            evidence = run_evidence(db_ev, run_id)
        finally:
            db_ev.close()
        user = (
            "Human review has produced new resolutions. They are now assertions in evidence.\n"
            f"Current evidence snapshot:\n{_dump(evidence)[:12000]}\n\n"
            "Continue the investigation. If evidence is sufficient, compare "
            "assertions yourself, create any remaining escalations, or call "
            "synthesize_explanation with citations. "
            "If material unresolved items remain, escalate again."
        )

    try:
        result = run_llm_loop(
            run_id=run_id,
            actor="orchestrator",
            system=ORCHESTRATOR_POLICY,
            user=user,
            tool_names=ORCHESTRATOR_TOOL_NAMES,
            extra_messages=extra,
            max_steps=28,
            allow_spawn=True,
        )
    except Exception as exc:
        db = session()
        inv = db.get(Investigation, run_id)
        if inv:
            inv.status = "failed"
            inv.pause_reason = str(exc)
            inv.updated_at = utcnow()
            db.commit()
        db.close()
        return {"error": str(exc), "run_id": run_id}

    db = session()
    inv = db.get(Investigation, run_id)
    if result.get("paused"):
        if inv:
            inv.status = "awaiting_human"
            inv.updated_at = utcnow()
            db.commit()
    elif inv and inv.status == "running":
        open_esc = len(
            db.scalars(
                select(Escalation).where(
                    Escalation.investigation_id == run_id,
                    Escalation.status == "open",
                )
            ).all()
        )
        if inv.explanation_id:
            inv.status = "completed"
            inv.completed_at = utcnow()
        elif open_esc:
            inv.status = "awaiting_human"
        else:
            inv.status = "completed"
            inv.completed_at = utcnow()
        inv.updated_at = utcnow()
        db.commit()
    status = inv.status if inv else "unknown"
    db.close()
    return {"run_id": run_id, "status": status, "result": result.get("text")}


def apply_resolution(
    escalation_id: str,
    decision: str,
    rationale: str,
    reviewer: str,
    chosen_assertion_id: str | None = None,
) -> dict:
    db = session()
    esc = db.get(Escalation, escalation_id)
    if not esc:
        db.close()
        return {"error": "unknown_escalation"}
    from cashe.models import Conflict

    conflict = db.get(Conflict, esc.conflict_id) if esc.conflict_id else None
    chosen_value = None
    if chosen_assertion_id:
        ast = db.get(SourceAssertion, chosen_assertion_id)
        if ast:
            chosen_value = json.loads(ast.value_json)
    payload = {
        "decision": decision,
        "chosen_assertion_id": chosen_assertion_id,
        "rationale": rationale,
        "reviewer": reviewer,
        "escalation_id": escalation_id,
        "conflict_id": esc.conflict_id,
    }
    art = persist_artifact(
        db,
        source_id="human-review",
        media_type="application/json",
        payload=payload,
        retrieval_method="human_resolution",
        run_id=esc.investigation_id,
        summary=f"Human resolution: {decision}",
    )
    ast = persist_assertion(
        db,
        artifact_id=art.id,
        run_id=esc.investigation_id,
        subject_type="resolution",
        subject_id=conflict.subject_id if conflict else escalation_id,
        field="human_decision",
        value={
            "decision": decision,
            "chosen_assertion_id": chosen_assertion_id,
            "chosen_value": chosen_value,
            "rationale": rationale,
        },
        authority="HUMAN_RESOLUTION",
        confidence="verified",
        notes=rationale,
    )
    resolution = HumanResolution(
        id=new_id("res"),
        conflict_id=esc.conflict_id or "",
        investigation_id=esc.investigation_id,
        decision=decision,
        chosen_assertion_id=chosen_assertion_id,
        rationale=rationale,
        reviewer=reviewer,
        effective_at=utcnow(),
        assertion_id=ast.id,
    )
    db.add(resolution)
    esc.status = "resolved"
    if conflict:
        conflict.status = "resolved"
    db.commit()
    emit_event(
        db,
        esc.investigation_id,
        "human_resolution",
        {
            "escalation_id": esc.id,
            "decision": decision,
            "chosen_assertion_id": chosen_assertion_id,
            "rationale": rationale,
        },
        actor="human",
    )
    run_id = esc.investigation_id
    db.close()
    return {"resolution_id": resolution.id, "assertion_id": ast.id, "investigation_id": run_id}

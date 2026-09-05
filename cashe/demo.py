"""Run a full Cashe investigation against Prism, including demo human resolutions."""

from __future__ import annotations

import json
import time

from sqlalchemy import select

from cashe.db import init_db, session
from cashe.models import Escalation, Explanation, Investigation, SourceAssertion
from cashe.orchestrator.loop import apply_resolution, continue_investigation, start_investigation
from cashe.seed import seed_static


def _open_escalations(run_id: str) -> list[Escalation]:
    db = session()
    rows = db.scalars(
        select(Escalation).where(Escalation.investigation_id == run_id, Escalation.status == "open")
    ).all()
    db.close()
    return list(rows)


def _assertions(run_id: str) -> list[SourceAssertion]:
    db = session()
    rows = db.scalars(select(SourceAssertion).where(SourceAssertion.run_id == run_id)).all()
    db.close()
    return list(rows)


def resolve_demo_packets(run_id: str) -> None:
    assertions = _assertions(run_id)
    for esc in _open_escalations(run_id):
        title = (esc.title or "").lower()
        packet = json.loads(esc.packet_json)
        if "bluepeak" in title or "legal" in title or "entity" in title:
            chosen = None
            for ast in assertions:
                if ast.subject_id == "INV-BP-2088" and ast.field == "legal_entity" and ast.authority == "BOOKS":
                    chosen = ast.id
                    break
            apply_resolution(
                esc.id,
                decision="choose_assertion",
                rationale=(
                    "The accounting entity Cashe Software, Inc. is correct. "
                    "Cashe Holdings LLC is the customer-side submission error on the portal."
                ),
                reviewer="demo-operator",
                chosen_assertion_id=chosen,
            )
        else:
            apply_resolution(
                esc.id,
                decision="approve_provisionally",
                rationale=(
                    packet.get("likely_interpretation")
                    or "Accept HarborLine procurement-review status as provisional until documentary corroboration arrives."
                ),
                reviewer="demo-operator",
            )


def run_demo(question: str = "Why did cash decrease in September?") -> dict:
    init_db()
    seed_static()
    run_id = start_investigation(question)
    print(f"investigation {run_id}")
    first = continue_investigation(run_id, resume=False)
    print(f"status after first pass: {first}")
    if first.get("status") == "awaiting_human" or _open_escalations(run_id):
        resolve_demo_packets(run_id)
        print("recorded demo human resolutions")
        second = continue_investigation(run_id, resume=True)
        print(f"status after resume: {second.get('status')}")
    db = session()
    inv = db.get(Investigation, run_id)
    expl = db.get(Explanation, inv.explanation_id) if inv and inv.explanation_id else None
    db.close()
    out = {
        "run_id": run_id,
        "status": first.get("status"),
        "explanation": json.loads(expl.body_json) if expl else None,
    }
    print(json.dumps(out, indent=2, default=str)[:8000])
    return out


if __name__ == "__main__":
    run_demo()

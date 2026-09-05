from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from cashe.config import settings
from cashe.db import init_db, session
from cashe.fixtures.statements import sequential_variance, statement_with_recon
from cashe.ids import iso
from cashe.models import (
    Escalation,
    Explanation,
    Investigation,
    InvestigationEvent,
    RawArtifact,
    Sop,
    SopRun,
    SourceRegistry,
)
from cashe.money import usd
from cashe.orchestrator.loop import apply_resolution, continue_investigation, start_investigation
from cashe.seed import seed_static
from cashe.sources import bluepeak, procureflow
from cashe.store import as_of_assertions, current_assertions, source_dict

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.filters["usd"] = usd

app = FastAPI(title="Cashe")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

_jobs: dict[str, asyncio.Task] = {}


@app.on_event("startup")
def _startup() -> None:
    init_db()
    seed_static()


def _inv_payload(inv: Investigation) -> dict:
    return {
        "id": inv.id,
        "question": inv.question,
        "status": inv.status,
        "created_at": iso(inv.created_at),
        "updated_at": iso(inv.updated_at),
        "completed_at": iso(inv.completed_at) if inv.completed_at else None,
        "explanation_id": inv.explanation_id,
        "pause_reason": inv.pause_reason,
    }


async def _run_job(run_id: str, resume: bool = False) -> None:
    await asyncio.to_thread(continue_investigation, run_id, resume=resume)


class InvestigateBody(BaseModel):
    question: str = "Why did cash decrease in September?"


class ResolveBody(BaseModel):
    decision: str
    rationale: str
    reviewer: str = "operator"
    chosen_assertion_id: str | None = None
    resume: bool = True


class LayoutBody(BaseModel):
    mode: str


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = session()
    investigations = db.scalars(select(Investigation).order_by(Investigation.created_at.desc())).all()
    db.close()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "august": statement_with_recon("2026-08"),
            "september": statement_with_recon("2026-09"),
            "variance": sequential_variance(),
            "investigations": investigations,
        },
    )


@app.get("/investigations/{run_id}", response_class=HTMLResponse)
def investigation_page(request: Request, run_id: str):
    db = session()
    inv = db.get(Investigation, run_id)
    if not inv:
        db.close()
        raise HTTPException(404)
    explanation = db.get(Explanation, inv.explanation_id) if inv.explanation_id else None
    escalations = db.scalars(select(Escalation).where(Escalation.investigation_id == run_id)).all()
    db.close()
    body = json.loads(explanation.body_json) if explanation else None
    return templates.TemplateResponse(
        "investigation.html",
        {
            "request": request,
            "inv": inv,
            "explanation": explanation,
            "body": body,
            "escalations": escalations,
        },
    )


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    db = session()
    rows = db.scalars(select(SourceRegistry)).all()
    db.close()
    return templates.TemplateResponse(
        "sources.html",
        {"request": request, "sources": [source_dict(r) for r in rows]},
    )


@app.get("/sops", response_class=HTMLResponse)
def sops_page(request: Request):
    db = session()
    sops = db.scalars(select(Sop)).all()
    runs = db.scalars(select(SopRun).order_by(SopRun.created_at.desc())).all()
    db.close()
    return templates.TemplateResponse("sops.html", {"request": request, "sops": sops, "runs": runs})


@app.get("/escalations", response_class=HTMLResponse)
def escalations_page(request: Request):
    db = session()
    rows = db.scalars(select(Escalation).order_by(Escalation.created_at.desc())).all()
    db.close()
    packets = []
    for row in rows:
        packets.append({**row.__dict__, "packet": json.loads(row.packet_json)})
    return templates.TemplateResponse("escalations.html", {"request": request, "escalations": packets})


@app.get("/evidence/{artifact_id}", response_class=HTMLResponse)
def evidence_page(request: Request, artifact_id: str):
    db = session()
    art = db.get(RawArtifact, artifact_id)
    db.close()
    if not art:
        raise HTTPException(404)
    payload = json.loads(Path(art.storage_path).read_text())
    return templates.TemplateResponse(
        "evidence.html",
        {"request": request, "artifact": art, "payload": json.dumps(payload, indent=2, default=str)},
    )


@app.post("/api/investigations")
async def api_start(body: InvestigateBody):
    run_id = start_investigation(body.question)
    _jobs[run_id] = asyncio.create_task(_run_job(run_id, resume=False))
    return {"id": run_id, "status": "running"}


@app.get("/api/investigations/{run_id}")
def api_get(run_id: str):
    db = session()
    inv = db.get(Investigation, run_id)
    if not inv:
        db.close()
        raise HTTPException(404)
    payload = _inv_payload(inv)
    if inv.explanation_id:
        expl = db.get(Explanation, inv.explanation_id)
        payload["explanation"] = json.loads(expl.body_json) if expl else None
    db.close()
    return payload


@app.get("/api/investigations/{run_id}/events")
def api_events(run_id: str, after: int = 0):
    db = session()
    rows = db.scalars(
        select(InvestigationEvent)
        .where(InvestigationEvent.investigation_id == run_id, InvestigationEvent.seq > after)
        .order_by(InvestigationEvent.seq)
    ).all()
    db.close()
    return {
        "events": [
            {
                "id": e.id,
                "seq": e.seq,
                "event_type": e.event_type,
                "actor": e.actor,
                "payload": json.loads(e.payload_json),
                "created_at": iso(e.created_at),
            }
            for e in rows
        ]
    }


@app.get("/api/explanations/{explanation_id}")
def api_explanation(explanation_id: str):
    db = session()
    expl = db.get(Explanation, explanation_id)
    db.close()
    if not expl:
        raise HTTPException(404)
    return json.loads(expl.body_json)


@app.get("/api/escalations")
def api_escalations():
    db = session()
    rows = db.scalars(select(Escalation).order_by(Escalation.created_at.desc())).all()
    db.close()
    return {
        "escalations": [
            {
                "id": e.id,
                "investigation_id": e.investigation_id,
                "title": e.title,
                "kind": e.kind,
                "status": e.status,
                "materiality_cents": e.materiality_cents,
                "recommended_action": e.recommended_action,
                "packet": json.loads(e.packet_json),
            }
            for e in rows
        ]
    }


@app.post("/api/escalations/{escalation_id}/resolve")
async def api_resolve(escalation_id: str, body: ResolveBody):
    result = apply_resolution(
        escalation_id,
        decision=body.decision,
        rationale=body.rationale,
        reviewer=body.reviewer,
        chosen_assertion_id=body.chosen_assertion_id,
    )
    if result.get("error"):
        raise HTTPException(404, result["error"])
    if body.resume:
        run_id = result["investigation_id"]
        db = session()
        remaining = db.scalars(
            select(Escalation).where(
                Escalation.investigation_id == run_id,
                Escalation.status == "open",
            )
        ).all()
        db.close()
        if not remaining:
            _jobs[run_id] = asyncio.create_task(_run_job(run_id, resume=True))
    return result


@app.get("/api/assertions/current")
def api_current():
    db = session()
    rows = current_assertions(db)
    db.close()
    return {"view": "current", "assertions": rows}


@app.get("/api/assertions/as-of")
def api_as_of(at: str):
    moment = datetime.fromisoformat(at.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    db = session()
    rows = as_of_assertions(db, moment)
    db.close()
    return {"view": "as_of", "at": at, "assertions": rows}


@app.post("/api/mock/bluepeak/layout-mode")
def api_layout(body: LayoutBody):
    return bluepeak.set_layout(body.mode)


@app.get("/mock/procureflow/api/v1/invoices/{invoice_number}")
def mock_pf_invoice(invoice_number: str, request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return procureflow.get_invoice(invoice_number)


@app.get("/mock/procureflow/api/v1/invoices/{invoice_number}/timeline")
def mock_pf_timeline(invoice_number: str, request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return procureflow.get_invoice_timeline(invoice_number)


@app.get("/mock/procureflow/api/v1/remittances")
def mock_pf_remittances(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return procureflow.list_remittances()


@app.get("/mock/bluepeak/login", response_class=HTMLResponse)
def mock_bp_login(request: Request):
    return templates.TemplateResponse("bluepeak_login.html", {"request": request, "layout": bluepeak.layout()})


@app.get("/mock/bluepeak/dashboard", response_class=HTMLResponse)
def mock_bp_dash(request: Request):
    return templates.TemplateResponse("bluepeak_dashboard.html", {"request": request, "layout": bluepeak.layout()})


@app.get("/mock/bluepeak/invoices", response_class=HTMLResponse)
def mock_bp_invoices(request: Request):
    view = bluepeak.invoice_view()
    return templates.TemplateResponse(
        "bluepeak_invoices.html",
        {"request": request, "layout": bluepeak.layout(), "invoice": view},
    )


@app.get("/mock/bluepeak/invoices/{invoice_number}", response_class=HTMLResponse)
def mock_bp_invoice(request: Request, invoice_number: str):
    view = bluepeak.invoice_view(invoice_number)
    if view.get("error"):
        raise HTTPException(404)
    return templates.TemplateResponse(
        "bluepeak_invoice.html",
        {"request": request, "layout": bluepeak.layout(), "invoice": view},
    )


def run() -> None:
    import uvicorn

    uvicorn.run("cashe.main:app", host=settings.cashe_host, port=settings.cashe_port, reload=False)

"""Operator board: bank SSOT, live channel, and an evidence graph."""

from __future__ import annotations

import json
from typing import Any

import httpx

from cashe.config import settings
from cashe.fixtures.statements import sequential_variance, statement_with_recon
from cashe.fixtures.world import ACCOUNTING_INVOICES, SOURCES
from sqlalchemy import select

from cashe.ids import iso
from cashe.models import Escalation, Explanation, Investigation, InvestigationEvent, RawArtifact, SourceAssertion
from cashe.store import assertion_dict, read_artifact_payload, run_evidence
from cashe.voice.realtime_common import get_last_call

_METHOD_KIND = {
    "mcp": "mcp",
    "api": "api",
    "browser": "browser",
    "browser_mocked": "browser",
    "voice": "voice",
    "voice_live": "voice",
    "voice_mocked": "voice",
}

_INVOICES = {i["invoice_number"]: i for i in ACCOUNTING_INVOICES}
_SOURCES = {s["source_id"]: s for s in SOURCES}


def _short(name: str) -> str:
    return (
        name.replace(" Group", "")
        .replace(" Labs", "")
        .replace(" Co.", "")
        .replace(" Software, Inc.", "")
        .strip()
    )


def invoice_name(invoice_number: str) -> str:
    row = _INVOICES.get(invoice_number) or {}
    return _short(row.get("customer") or invoice_number)


def source_name(source_id: str) -> str:
    row = _SOURCES.get(source_id) or {}
    org = _short(row.get("organization") or source_id)
    kind = row.get("product_family") or ""
    if "voice" in kind:
        return f"{org} phone"
    if "portal" in kind or "vendor" in source_id:
        return f"{org} portal"
    if source_id.endswith("-mcp") or "erp" in kind:
        return "Cashe books"
    if "api" in kind or "procure" in kind:
        return f"{org} API"
    return org


def source_detail(source_id: str) -> str:
    row = _SOURCES.get(source_id) or {}
    kind = row.get("product_family") or ""
    if source_id.endswith("-mcp") or "erp" in kind:
        return "ERP · MCP"
    if "voice" in kind:
        return "Voice"
    if "portal" in kind or "vendor" in source_id:
        return "Browser"
    if "api" in kind or "procure" in kind:
        return "API"
    return (row.get("notes") or kind or source_id)[:42]


def invoice_detail(invoice_number: str, fact: str = "") -> str:
    row = _INVOICES.get(invoice_number) or {}
    status = fact or row.get("status") or "OPEN"
    return f"{invoice_number} · {status}"


def _money(cents: int) -> str:
    return f"${cents / 100:,.0f}"


def _fact(field: str, value: Any) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    if field == "amount_cents" and isinstance(value, int):
        return _money(value)
    text = str(value).strip()
    if field in {"status", "dispute_reason", "legal_entity", "reason"}:
        return text
    if len(text) > 42:
        return text[:40] + "…"
    return text


def bank_ssot() -> dict:
    aug = statement_with_recon("2026-08")
    sep = statement_with_recon("2026-09")
    variance = sequential_variance()
    return {
        "bank": sep["bank"],
        "account": sep["account_name"],
        "entity": sep["account_owner"],
        "currency": sep["currency"],
        "august_close_cents": aug["closing_booked_balance_cents"],
        "september_close_cents": sep["closing_booked_balance_cents"],
        "invariant_holds": bool(sep["reconciliation"]["invariant_holds"]),
        "variance": {
            "ending_cash_change_cents": variance["ending_cash_change_cents"],
            "net_generation_deterioration_cents": variance["net_generation_deterioration_cents"],
            "collections_shortfall_cents": variance["collections_shortfall_cents"],
            "outflow_increase_cents": variance["outflow_increase_cents"],
        },
        "open_invoices": [
            {
                "invoice_number": inv["invoice_number"],
                "customer": inv["customer"],
                "amount_cents": inv["amount_cents"],
            }
            for inv in ACCOUNTING_INVOICES
        ],
    }


def live_voice() -> dict:
    for base in (settings.local_server, settings.local_server_twilio):
        try:
            response = httpx.get(f"{base.rstrip('/')}/transcript", timeout=0.7)
            if response.is_success:
                data = response.json()
                if data.get("status") == "in_progress":
                    data["provider"] = "bridge"
                    return data
        except httpx.HTTPError:
            continue
    last = get_last_call()
    if last.get("status") == "in_progress":
        last = dict(last)
        last["provider"] = "local"
        return last
    return {"status": "idle", "transcript": []}


def _layout(layers: list[list[dict]]) -> None:
    width = 920
    height = 280
    ys = [48, 140, 232]
    for i, layer in enumerate(layers):
        if not layer:
            continue
        y = ys[min(i, len(ys) - 1)]
        n = len(layer)
        span = width - 120
        for j, node in enumerate(layer):
            node["x"] = 60 + (span * (j + 0.5) / n)
            node["y"] = y
            node["w"] = min(168, span / max(n, 1) - 16)
    _ = height


_ACTIVE = {
    "voice": ("src:harborline-ap-desk", "inv:INV-HL-3301"),
    "browser": ("src:bluepeak-vendor-center", "inv:INV-BP-2088"),
    "api": ("src:novaworks-procureflow", "inv:INV-NW-1042"),
    "mcp": ("src:cashe-accounting-mcp",),
}

_CHANNEL_SEEDS = {
    "voice": (
        ("inv:INV-HL-3301", "invoice", "on the line", 1),
        ("src:harborline-ap-desk", "voice", "live", 2),
    ),
    "browser": (
        ("inv:INV-BP-2088", "invoice", "portal", 1),
        ("src:bluepeak-vendor-center", "browser", "live", 2),
    ),
    "api": (
        ("inv:INV-NW-1042", "invoice", "api", 1),
        ("src:novaworks-procureflow", "api", "live", 2),
    ),
    "mcp": (("src:cashe-accounting-mcp", "mcp", "live", 2),),
}


def build_graph(evidence: dict, channel: str | None = None) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(node_id: str, **kwargs) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, **kwargs}

    add("bank", kind="bank", label="Northstar", detail="Settled cash", layer=0)

    artifacts = {a["id"]: a for a in evidence.get("artifacts") or []}
    facts: dict[str, list[str]] = {}
    linked: set[tuple[str, str]] = set()
    for ast in evidence.get("assertions") or []:
        if ast.get("field") == "transcript":
            continue
        art = artifacts.get(ast.get("artifact_id") or "")
        if not art:
            continue
        number = str(ast.get("subject_id") or "")
        if ast.get("subject_type") != "invoice" and number not in _INVOICES:
            continue
        method = _METHOD_KIND.get(art.get("retrieval_method") or "", "source")
        sid = f"src:{art['source_id']}"
        add(
            sid,
            kind=method,
            label=source_name(art["source_id"]),
            detail=source_detail(art["source_id"]),
            layer=2,
        )
        subject = f"inv:{number}"
        fact = _fact(ast.get("field") or "", ast.get("value"))
        if fact:
            facts.setdefault(subject, []).append(fact)
        amt = (_INVOICES.get(number) or {}).get("amount_cents")
        add(
            subject,
            kind="invoice",
            label=f"{invoice_name(number)}  {_money(amt)}" if amt else invoice_name(number),
            detail=invoice_detail(number),
            layer=1,
        )
        pair = (sid, subject)
        if pair not in linked:
            linked.add(pair)
            edges.append({"from": sid, "to": subject, "rel": "retrieved"})

    for nid, found in facts.items():
        if nid in nodes:
            nodes[nid]["detail"] = invoice_detail(nid.removeprefix("inv:"), found[0])

    for spec in _CHANNEL_SEEDS.get(channel or "", ()):
        nid, kind, detail, layer = spec
        if nid in nodes:
            continue
        if nid.startswith("inv:"):
            number = nid.split(":", 1)[1]
            amt = (_INVOICES.get(number) or {}).get("amount_cents")
            nodes[nid] = {
                "id": nid,
                "kind": kind,
                "label": f"{invoice_name(number)}  {_money(amt)}" if amt else invoice_name(number),
                "detail": invoice_detail(number, detail),
                "layer": layer,
            }
        else:
            sid = nid.removeprefix("src:")
            nodes[nid] = {
                "id": nid,
                "kind": kind,
                "label": source_name(sid),
                "detail": source_detail(sid),
                "layer": layer,
            }

    for node in list(nodes.values()):
        if node["kind"] == "invoice":
            pair = ("bank", node["id"], "unsettled")
            if not any(e["from"] == pair[0] and e["to"] == pair[1] and e["rel"] == pair[2] for e in edges):
                edges.append({"from": pair[0], "to": pair[1], "rel": pair[2]})

    seeds = _CHANNEL_SEEDS.get(channel or "", ())
    srcs = [s[0] for s in seeds if s[0].startswith("src:")]
    invs = [s[0] for s in seeds if s[0].startswith("inv:")]
    for sid in srcs:
        for iid in invs:
            if sid in nodes and iid in nodes and not any(e["from"] == sid and e["to"] == iid for e in edges):
                edges.append({"from": sid, "to": iid, "rel": "retrieved"})

    active = set(_ACTIVE.get(channel or "", ()))
    for node in nodes.values():
        node["active"] = node["id"] in active
    for edge in edges:
        edge["active"] = edge["from"] in active or edge["to"] in active

    layers: list[list[dict]] = [[], [], []]
    for node in nodes.values():
        layers[min(int(node.get("layer") or 0), 2)].append(node)
    _layout(layers)
    return {"nodes": list(nodes.values()), "edges": edges}


def _now(events: list[dict]) -> dict:
    channel = None
    spawned: set[str] = set()
    text = "Waiting."
    for ev in events:
        kind = ev.get("event_type")
        payload = ev.get("payload") or {}
        actor = ev.get("actor") or "orchestrator"
        if kind == "started":
            text = payload.get("question") or "Started."
        elif kind == "llm_message":
            text = (payload.get("text") or "")[:220]
            if str(actor).startswith("subagent:"):
                channel = str(actor).split(":", 1)[1]
        elif kind == "tool_call":
            text = f"{actor} → {payload.get('tool')}"
            tool = str(payload.get("tool") or "")
            if "voice" in tool:
                channel = "voice"
            elif "browser" in tool:
                channel = "browser"
            elif "api" in tool or tool.startswith("pf_") or "invoice" in tool:
                channel = channel or "api"
        elif kind == "tool_result":
            text = f"{payload.get('tool')} {'ok' if payload.get('ok') else 'err'}"
        elif kind == "subagent_spawn":
            channel = payload.get("role")
            spawned.add(str(channel))
            text = f"{channel}: {payload.get('goal') or 'working'}"
        elif kind == "subagent_complete":
            role = payload.get("role")
            spawned.discard(str(role))
            text = f"{role} finished"
            if channel == role:
                channel = None
        elif kind == "escalation":
            text = payload.get("title") or "Escalation"
            channel = "human"
        elif kind == "pause":
            text = payload.get("reason") or "Paused for a human"
            channel = "human"
        elif kind == "explanation":
            text = payload.get("headline") or "Explanation ready"
            channel = None
    if spawned and not channel:
        channel = next(iter(spawned))
    return {"text": text, "channel": channel}


def _browser_from_evidence(db, evidence: dict) -> dict | None:
    arts = [a for a in evidence.get("artifacts") or [] if "browser" in (a.get("retrieval_method") or "")]
    if not arts:
        return None
    row = db.get(RawArtifact, arts[-1]["id"])
    payload = read_artifact_payload(row) if row else {}
    return {
        "invoice_number": payload.get("invoice_number"),
        "steps": payload.get("action_trace") or payload.get("steps") or [],
        "extracted": payload.get("extracted") or {},
        "checks": payload.get("checks") or {},
        "artifact_id": arts[-1]["id"],
    }


def _fmt_choice_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)
        return text[:80] + "…" if len(text) > 80 else text
    return str(value)


def _escalations(db, run_id: str) -> list[dict]:
    rows = db.scalars(
        select(Escalation)
        .where(Escalation.investigation_id == run_id)
        .order_by(Escalation.created_at)
    ).all()
    packets = []
    for esc in rows:
        packet = json.loads(esc.packet_json or "{}")
        ids = json.loads(esc.assertion_ids_json or "[]") or packet.get("assertion_ids") or []
        choices = []
        for aid in ids:
            ast = db.get(SourceAssertion, aid)
            if not ast:
                continue
            row = assertion_dict(ast)
            if row["field"] == "transcript":
                continue
            choices.append(
                {
                    "id": row["id"],
                    "field": row["field"],
                    "value": row["value"],
                    "label": _fmt_choice_value(row["value"]),
                    "authority": row["authority"],
                    "confidence": row["confidence"],
                    "subject_id": row["subject_id"],
                }
            )
        packets.append(
            {
                "id": esc.id,
                "title": esc.title,
                "kind": esc.kind,
                "status": esc.status,
                "recommended_action": esc.recommended_action,
                "materiality_cents": esc.materiality_cents,
                "likely_interpretation": packet.get("likely_interpretation") or "",
                "remaining_uncertainty": packet.get("remaining_uncertainty") or "",
                "choices": choices,
            }
        )
    return packets


def board_payload(db, run_id: str) -> dict[str, Any]:
    inv = db.get(Investigation, run_id)
    if not inv:
        return {"error": "not_found"}
    rows = db.scalars(
        select(InvestigationEvent)
        .where(InvestigationEvent.investigation_id == run_id)
        .order_by(InvestigationEvent.seq)
    ).all()
    events = [
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
    evidence = run_evidence(db, run_id)
    now = _now(events)
    voice = live_voice()
    if voice.get("status") == "in_progress":
        now["channel"] = "voice"
    explanation = None
    if inv.explanation_id:
        expl = db.get(Explanation, inv.explanation_id)
        explanation = json.loads(expl.body_json) if expl else None
    return {
        "investigation": {
            "id": inv.id,
            "question": inv.question,
            "status": inv.status,
            "pause_reason": inv.pause_reason,
            "updated_at": iso(inv.updated_at),
        },
        "ssot": bank_ssot(),
        "now": now,
        "events": events[-80:],
        "evidence": evidence,
        "graph": build_graph(evidence, now.get("channel")),
        "live": {
            "voice": voice if voice.get("status") == "in_progress" else {"status": "idle", "transcript": []},
            "browser": _browser_from_evidence(db, evidence) if now.get("channel") == "browser" else None,
        },
        "escalations": _escalations(db, run_id),
        "explanation": explanation,
    }

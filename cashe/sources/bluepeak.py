from cashe.fixtures.world import BLUEPEAK_INVOICE, LAYOUT_MODE

LABELS = {
    "default": {
        "collection": "Invoices",
        "disputed": "Disputed",
        "needs_attention": "Disputed",
    },
    "relabeled": {
        "collection": "Billing Documents",
        "disputed": "Needs Attention",
        "needs_attention": "Needs Attention",
    },
}


def layout() -> dict:
    mode = LAYOUT_MODE["mode"]
    return {"mode": mode, **LABELS.get(mode, LABELS["default"])}


def set_layout(mode: str) -> dict:
    if mode not in LABELS:
        return {"error": "unknown_mode", "mode": mode}
    LAYOUT_MODE["mode"] = mode
    return layout()


def invoice_view(invoice_number: str = "INV-BP-2088") -> dict:
    labels = layout()
    inv = BLUEPEAK_INVOICE
    if invoice_number != inv["invoice_number"]:
        return {"error": "not_found", "invoice_number": invoice_number}
    status_label = labels["disputed"] if inv["status"] == "DISPUTED" else inv["status"]
    return {
        "portal": "BluePeak Vendor Center",
        "layout": labels,
        "invoice_number": inv["invoice_number"],
        "po_number": inv["po_number"],
        "amount_cents": inv["amount_cents"],
        "currency": inv["currency"],
        "legal_entity": inv["legal_entity_submitted"],
        "status": inv["status"],
        "status_label": status_label,
        "rejection_count": inv["rejection_count"],
        "dispute_reason": inv["dispute_reason"],
        "customer_comments": inv["customer_comments"],
        "timeline": inv["timeline"],
        "mutating_actions_available": False,
    }


def mock_browser_run(invoice_number: str, sop: dict | None, step_budget: int) -> dict:
    """Return a completed bounded-browser investigation without a live browser agent."""
    view = invoice_view(invoice_number)
    if view.get("error"):
        return view
    trace = [
        {"step": 1, "intent": "authenticate with the registered read-only identity", "result": "session established"},
        {
            "step": 2,
            "intent": "open the invoice or billing document collection",
            "result": f"opened {view['layout']['collection']}",
        },
        {
            "step": 3,
            "intent": "find the invoice matching the supplied invoice number",
            "result": f"located {invoice_number}",
        },
        {
            "step": 4,
            "intent": "capture status, dispute reason, legal entity, and complete timeline",
            "result": "timeline exhausted; two rejections captured",
        },
    ]
    checks = {
        "invoice_number_matches": view["invoice_number"] == invoice_number,
        "customer_matches": True,
        "amount_matches_accounting_record": view["amount_cents"] == 21_000_000,
        "timeline_exhausted": len(view["timeline"]) >= 4,
    }
    return {
        "mocked": True,
        "agent": "browser",
        "note": "Live browser agent is stubbed. Evidence is taken from the allowlisted BluePeak portal fixture.",
        "source_id": "bluepeak-vendor-center",
        "sop_id": sop["sop_id"] if sop else None,
        "sop_version": sop["version"] if sop else None,
        "step_budget": step_budget,
        "steps_used": len(trace),
        "action_trace": trace,
        "extracted": view,
        "checks": checks,
        "checks_passed": all(checks.values()),
        "proposed_sop_patch": {
            "learned_hints": [
                f"Collection label observed: {view['layout']['collection']}",
                f"Dispute label observed: {view['layout']['disputed']}",
            ]
        },
        "authority": "WORKFLOW",
        "host_allowlist_honored": True,
        "mutating_action_attempted": False,
    }

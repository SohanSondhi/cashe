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

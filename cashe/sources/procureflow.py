from cashe.fixtures.world import PROCUREFLOW

ALLOWED = {"get_invoice", "get_invoice_timeline", "list_remittances"}


def get_invoice(invoice_number: str) -> dict:
    row = PROCUREFLOW.get(invoice_number)
    if not row:
        return {"error": "not_found", "invoice_number": invoice_number}
    return {
        "invoice_number": row["invoice_number"],
        "supplier_name": row["supplier_name"],
        "customer": row["customer"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "status": row["status"],
        "po_number": row["po_number"],
        "po_available_on": row["po_available_on"],
        "delay_days": row["delay_days"],
        "blocking_reason": row["blocking_reason"],
        "current_owner": row["current_owner"],
    }


def get_invoice_timeline(invoice_number: str) -> dict:
    row = PROCUREFLOW.get(invoice_number)
    if not row:
        return {"error": "not_found", "invoice_number": invoice_number}
    return {
        "invoice_number": invoice_number,
        "status": row["status"],
        "first_attempted_submission": row["first_attempted_submission"],
        "successful_submission": row["successful_submission"],
        "delay_days": row["delay_days"],
        "blocking_reason": row["blocking_reason"],
        "timeline": row["timeline"],
    }


def list_remittances() -> dict:
    return {"remittances": [], "note": "No remittances issued for INV-NW-1042 in September."}


def invoke(operation: str, parameters: dict) -> dict:
    if operation not in ALLOWED:
        return {"error": "operation_not_registered", "operation": operation, "allowed": sorted(ALLOWED)}
    if operation == "get_invoice":
        return get_invoice(parameters["invoice_number"])
    if operation == "get_invoice_timeline":
        return get_invoice_timeline(parameters["invoice_number"])
    if operation == "list_remittances":
        return list_remittances()
    return {"error": "unhandled"}

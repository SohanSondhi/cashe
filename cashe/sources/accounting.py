import inspect

from cashe.fixtures.world import ACCOUNTING_INVOICES, CUSTOMERS


def list_open_invoices(entity: str = "CASH-US", as_of: str = "2026-09-30", minimum_amount_cents: int = 0) -> dict:
    invoices = [
        inv
        for inv in ACCOUNTING_INVOICES
        if inv["entity_code"] == entity and inv["status"] == "OPEN" and inv["amount_cents"] >= minimum_amount_cents
    ]
    total = sum(i["amount_cents"] for i in invoices)
    return {
        "source": "cashe-accounting-mcp",
        "tool": "list_open_invoices",
        "entity": entity,
        "as_of": as_of,
        "invoices": invoices,
        "total_open_cents": total,
        "count": len(invoices),
        "authority": "BOOKS",
    }


def get_invoice(invoice_number: str) -> dict:
    for inv in ACCOUNTING_INVOICES:
        if inv["invoice_number"] == invoice_number:
            return {"source": "cashe-accounting-mcp", "tool": "get_invoice", "invoice": inv, "authority": "BOOKS"}
    return {"error": "not_found", "invoice_number": invoice_number}


def get_customer(customer_id: str) -> dict:
    cust = CUSTOMERS.get(customer_id)
    if not cust:
        return {"error": "not_found", "customer_id": customer_id}
    return {"source": "cashe-accounting-mcp", "tool": "get_customer", "customer": cust, "authority": "BOOKS"}


def get_expected_receipts(entity: str = "CASH-US", period: str = "2026-09") -> dict:
    invoices = [
        inv
        for inv in ACCOUNTING_INVOICES
        if inv["entity_code"] == entity and inv["expected_settlement_period"] == period
    ]
    return {
        "source": "cashe-accounting-mcp",
        "tool": "get_expected_receipts",
        "entity": entity,
        "period": period,
        "receipts": invoices,
        "total_cents": sum(i["amount_cents"] for i in invoices),
        "authority": "BOOKS",
    }


MCP_TOOLS = {
    "list_open_invoices": list_open_invoices,
    "get_invoice": get_invoice,
    "get_customer": get_customer,
    "get_expected_receipts": get_expected_receipts,
}


def invoke(tool: str, arguments: dict) -> dict:
    fn = MCP_TOOLS.get(tool)
    if not fn:
        return {"error": "unknown_mcp_tool", "tool": tool, "available": list(MCP_TOOLS)}
    allowed = inspect.signature(fn).parameters
    filtered = {k: v for k, v in (arguments or {}).items() if k in allowed}
    return fn(**filtered)

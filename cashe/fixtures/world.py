"""Demo world: customers, invoices, portals, voice desk, source registry."""

ACCOUNTING_INVOICES = [
    {
        "invoice_number": "INV-NW-1042",
        "customer": "NovaWorks Group",
        "customer_id": "cust-novaworks",
        "amount_cents": 24_000_000,
        "currency": "USD",
        "due_date": "2026-09-20",
        "issue_date": "2026-08-31",
        "legal_entity": "Cashe Software, Inc.",
        "entity_code": "CASH-US",
        "status": "OPEN",
        "po_number": "PO-NW-8891",
        "expected_settlement_period": "2026-09",
        "books_notes": "AR open. No cash application in September.",
    },
    {
        "invoice_number": "INV-BP-2088",
        "customer": "BluePeak Labs",
        "customer_id": "cust-bluepeak",
        "amount_cents": 21_000_000,
        "currency": "USD",
        "due_date": "2026-09-22",
        "issue_date": "2026-08-31",
        "legal_entity": "Cashe Software, Inc.",
        "entity_code": "CASH-US",
        "status": "OPEN",
        "po_number": "PO-BP-4410",
        "expected_settlement_period": "2026-09",
        "books_notes": "AR open. Books record billing entity as Cashe Software, Inc.",
    },
    {
        "invoice_number": "INV-HL-3301",
        "customer": "HarborLine Co.",
        "customer_id": "cust-harborline",
        "amount_cents": 17_000_000,
        "currency": "USD",
        "due_date": "2026-09-25",
        "issue_date": "2026-08-31",
        "legal_entity": "Cashe Software, Inc.",
        "entity_code": "CASH-US",
        "status": "OPEN",
        "po_number": "PO-HL-2207",
        "expected_settlement_period": "2026-09",
        "books_notes": "AR open. No remittance received.",
    },
]

CUSTOMERS = {
    "cust-novaworks": {
        "customer_id": "cust-novaworks",
        "name": "NovaWorks Group",
        "ap_system": "ProcureFlow",
        "source_id": "novaworks-procureflow",
    },
    "cust-bluepeak": {
        "customer_id": "cust-bluepeak",
        "name": "BluePeak Labs",
        "ap_system": "BluePeak Vendor Center",
        "source_id": "bluepeak-vendor-center",
    },
    "cust-harborline": {
        "customer_id": "cust-harborline",
        "name": "HarborLine Co.",
        "ap_system": "HarborLine AP service desk",
        "source_id": "harborline-ap-desk",
    },
}

PROCUREFLOW = {
    "INV-NW-1042": {
        "invoice_number": "INV-NW-1042",
        "supplier_name": "Cashe Software, Inc.",
        "customer": "NovaWorks Group",
        "amount_cents": 24_000_000,
        "currency": "USD",
        "status": "PENDING_APPROVAL",
        "po_number": "PO-NW-8891",
        "po_available_on": "2026-09-09",
        "first_attempted_submission": "2026-09-01T14:06:00+00:00",
        "successful_submission": "2026-09-10T11:22:00+00:00",
        "delay_days": 9,
        "blocking_reason": "Required purchase order was unavailable at first submission",
        "current_owner": "NovaWorks AP — plant 4",
        "timeline": [
            {
                "at": "2026-09-01T14:06:00+00:00",
                "event": "submission_rejected",
                "detail": "PO number required. No matching PO in ProcureFlow.",
            },
            {
                "at": "2026-09-09T09:40:00+00:00",
                "event": "po_released",
                "detail": "PO-NW-8891 released to supplier portal.",
            },
            {
                "at": "2026-09-10T11:22:00+00:00",
                "event": "submitted",
                "detail": "Invoice accepted against PO-NW-8891.",
            },
            {
                "at": "2026-09-10T11:23:00+00:00",
                "event": "routed_for_approval",
                "detail": "Status PENDING_APPROVAL. No payment scheduled.",
            },
        ],
    }
}

BLUEPEAK_INVOICE = {
    "invoice_number": "INV-BP-2088",
    "po_number": "PO-BP-4410",
    "amount_cents": 21_000_000,
    "currency": "USD",
    "legal_entity_submitted": "Cashe Holdings LLC",
    "expected_legal_entity": "Cashe Software, Inc.",
    "status": "DISPUTED",
    "rejection_count": 2,
    "dispute_reason": "Invoice submitted under Cashe Holdings LLC instead of Cashe Software, Inc.",
    "customer_comments": "Please resubmit under the contracted legal entity Cashe Software, Inc.",
    "timeline": [
        {
            "at": "2026-09-04T16:10:00+00:00",
            "event": "submitted",
            "detail": "Submitted as Cashe Holdings LLC.",
        },
        {
            "at": "2026-09-05T09:18:00+00:00",
            "event": "rejected",
            "detail": "Legal entity mismatch. Rejection 1 of 2.",
        },
        {
            "at": "2026-09-12T13:44:00+00:00",
            "event": "resubmitted",
            "detail": "Resubmitted; legal entity field still Cashe Holdings LLC.",
        },
        {
            "at": "2026-09-13T08:02:00+00:00",
            "event": "rejected",
            "detail": "Legal entity mismatch. Rejection 2 of 2. Status DISPUTED.",
        },
    ],
}

HARBORLINE_VOICE = {
    "invoice_number": "INV-HL-3301",
    "desk": "HarborLine AP service desk",
    "claimed_speaker": "Marta Chen, AP specialist",
    "status": "procurement_review",
    "reason": "PO arrived after the original invoice was sent",
    "promised_follow_up": "Email confirmation within one business day",
    "payment_date": None,
    "authority": "COMMUNICATION",
    "transcript": [
        {
            "ts": "2026-10-02T15:04:11+00:00",
            "speaker": "cashe",
            "text": "This is Cashe's collections desk calling about INV-HL-3301, $170,000, due September 25. Can you confirm current status?",
        },
        {
            "ts": "2026-10-02T15:04:28+00:00",
            "speaker": "marta_chen",
            "text": "I have it. It's in procurement review. The PO came in after the original invoice, so AP can't approve until procurement matches the document.",
        },
        {
            "ts": "2026-10-02T15:04:41+00:00",
            "speaker": "cashe",
            "text": "Is there a confirmed payment date, and can you send written confirmation?",
        },
        {
            "ts": "2026-10-02T15:04:55+00:00",
            "speaker": "marta_chen",
            "text": "No payment date yet. I'll email you confirmation of the procurement-review hold within one business day. I can't generate a remittance or an approved invoice from this desk.",
        },
    ],
}

SOURCES = [
    {
        "source_id": "cashe-accounting-mcp",
        "organization": "Cashe Software, Inc.",
        "product_family": "erp_subledger",
        "base_url": "http://localhost:8000/mcp/accounting",
        "allowed_hosts": ["localhost"],
        "entitlements": {"mcp": True, "api": False, "browser": False, "voice": False},
        "credential_ref": "mock://accounting/mcp",
        "permission": "read_only",
        "expected_artifacts": ["open_invoices", "expected_receipts", "customer_master"],
        "preferred_sop_id": None,
        "allowed_operations": ["list_open_invoices", "get_invoice", "get_customer", "get_expected_receipts"],
        "notes": "Internal ERP exposed as MCP. Authoritative for recorded books, not bank settlement.",
    },
    {
        "source_id": "novaworks-procureflow",
        "organization": "NovaWorks Group",
        "product_family": "procureflow",
        "base_url": "http://localhost:8000/mock/procureflow",
        "allowed_hosts": ["localhost"],
        "entitlements": {"mcp": False, "api": True, "browser": False, "voice": False},
        "credential_ref": "mock://novaworks/api-token",
        "permission": "read_only",
        "expected_artifacts": ["invoice_status", "invoice_timeline"],
        "preferred_sop_id": None,
        "allowed_operations": ["get_invoice", "get_invoice_timeline", "list_remittances"],
        "notes": "Customer AP platform. Cashe holds an API token. No MCP.",
    },
    {
        "source_id": "bluepeak-vendor-center",
        "organization": "BluePeak Labs",
        "product_family": "custom_ap_portal",
        "base_url": "http://localhost:8000/mock/bluepeak",
        "allowed_hosts": ["localhost"],
        "entitlements": {"mcp": False, "api": False, "browser": True, "voice": True},
        "credential_ref": "mock://bluepeak/read-only",
        "permission": "read_only",
        "expected_artifacts": ["invoice_status", "dispute_reason", "legal_entity"],
        "preferred_sop_id": "sop-bluepeak-status-v1",
        "allowed_operations": [],
        "notes": "Custom vendor portal. No usable customer API entitlement. Browser is the authorized machine path.",
    },
    {
        "source_id": "harborline-ap-desk",
        "organization": "HarborLine Co.",
        "product_family": "voice_ap_desk",
        "base_url": "http://localhost:8000/mock/harborline/voice",
        "allowed_hosts": ["localhost"],
        "entitlements": {"mcp": False, "api": False, "browser": False, "voice": True},
        "credential_ref": "mock://harborline/voice",
        "permission": "read_only",
        "expected_artifacts": ["invoice_status_claim", "follow_up_promise"],
        "preferred_sop_id": None,
        "allowed_operations": [],
        "notes": "No MCP, API, or portal in this incident. Voice desk is the only authorized channel. Browser portal unavailable.",
    },
]

BLUEPEAK_SOP = {
    "sop_id": "sop-bluepeak-status-v1",
    "source_id": "bluepeak-vendor-center",
    "goal_type": "retrieve_invoice_status",
    "version": 1,
    "status": "approved",
    "parameters": ["invoice_number"],
    "steps": [
        {"intent": "authenticate with the registered read-only identity"},
        {"intent": "open the invoice or billing document collection"},
        {"intent": "find the invoice matching the supplied invoice number"},
        {"intent": "capture status, dispute reason, legal entity, and complete timeline"},
    ],
    "verification": [
        "invoice_number_matches",
        "customer_matches",
        "amount_matches_accounting_record",
        "timeline_exhausted",
    ],
    "learned_hints": [
        "The invoice collection may be labeled Invoices or Billing Documents",
        "Disputed invoices may appear as Needs Attention after a layout change",
    ],
    "created_from_run_id": "run-demo-seed",
}

LAYOUT_MODE = {"mode": "default"}

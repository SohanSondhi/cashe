from datetime import datetime, timezone

from cashe.money import usd


def _txn(
    transaction_id: str,
    credit_debit_indicator: str,
    amount_cents: int,
    booking_date: str,
    counterparty_name: str,
    remittance_information: str,
    bank_transaction_code: str,
    customer_reference: str = "",
) -> dict:
    return {
        "transaction_id": transaction_id,
        "credit_debit_indicator": credit_debit_indicator,
        "amount_cents": amount_cents,
        "booking_date": booking_date,
        "value_date": booking_date,
        "bank_transaction_code": bank_transaction_code,
        "bank_reference": transaction_id.replace("txn-", "NSB-"),
        "customer_reference": customer_reference,
        "counterparty_name": counterparty_name,
        "remittance_information": remittance_information,
    }


AUGUST = {
    "statement_id": "stmt-2026-08-nsb-1842",
    "account_id": "acct-nsb-1842",
    "account_owner": "Cashe Software, Inc.",
    "bank": "Northstar Commercial Bank",
    "account_name": "Operating ••1842",
    "entity_code": "CASH-US",
    "currency": "USD",
    "period": "2026-08",
    "period_start": "2026-08-01",
    "period_end": "2026-08-31",
    "opening_booked_balance_cents": 290_000_000,
    "closing_booked_balance_cents": 320_000_000,
    "generated_at": "2026-09-01T08:12:00+00:00",
    "transactions": [
        _txn("txn-aug-c01", "CRDT", 42_000_000, "2026-08-04", "Apex Dynamics", "INV-AX-991 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c02", "CRDT", 38_000_000, "2026-08-06", "Meridian Health", "INV-MH-440 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c03", "CRDT", 31_000_000, "2026-08-08", "LumenForge", "INV-LF-118 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c04", "CRDT", 28_000_000, "2026-08-11", "Keystone Retail", "INV-KR-072 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c05", "CRDT", 45_000_000, "2026-08-12", "OrbitPay", "Card settlement batch 08", "PMNT-RCDT"),
        _txn("txn-aug-c06", "CRDT", 26_000_000, "2026-08-15", "Helios Manufacturing", "INV-HM-203 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c07", "CRDT", 25_000_000, "2026-08-18", "Northwind Partners", "INV-NP-055 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c08", "CRDT", 1_800_000, "2026-08-19", "Vellum Systems", "Credit memo reversal", "PMNT-RCDT"),
        _txn("txn-aug-c09", "CRDT", 19_000_000, "2026-08-21", "Stratton Media", "INV-SM-310 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c10", "CRDT", 18_000_000, "2026-08-25", "Vellum Systems", "INV-VS-087 settlement", "PMNT-RCDT"),
        _txn("txn-aug-c11", "CRDT", 10_000_000, "2026-08-28", "Cashe Holdings LLC", "Intercompany funding", "PMNT-ICDT"),
        _txn("txn-aug-c12", "CRDT", 1_200_000, "2026-08-31", "Northstar Commercial Bank", "Operating account interest", "ACMT-MCOP"),
        _txn("txn-aug-d01", "DBIT", 8_500_000, "2026-08-01", "Harbor Realty", "HQ lease August", "PMNT-ICDT"),
        _txn("txn-aug-d02", "DBIT", 4_500_000, "2026-08-03", "Northshore Mutual", "D&O / property insurance", "PMNT-ICDT"),
        _txn("txn-aug-d03", "DBIT", 14_500_000, "2026-08-05", "Amazon Web Services", "Cloud invoice AWS-08", "PMNT-ICDT"),
        _txn("txn-aug-d04", "DBIT", 22_000_000, "2026-08-07", "Datacore Systems", "INV-DC-441 infrastructure", "PMNT-ICDT"),
        _txn("txn-aug-d05", "DBIT", 31_000_000, "2026-08-14", "US Treasury", "Q estimated federal tax", "PMNT-ICDT"),
        _txn("txn-aug-d06", "DBIT", 89_000_000, "2026-08-15", "Cashe Payroll Trust", "Semi-monthly payroll", "PMNT-SALA"),
        _txn("txn-aug-d07", "DBIT", 18_000_000, "2026-08-15", "Fidelity Benefits", "401k + medical", "PMNT-SALA"),
        _txn("txn-aug-d08", "DBIT", 21_000_000, "2026-08-20", "Fieldwork Contractors", "August contractor draw", "PMNT-ICDT"),
        _txn("txn-aug-d09", "DBIT", 16_500_000, "2026-08-22", "Northstar Media Buy", "Demand-gen August", "PMNT-ICDT"),
        _txn("txn-aug-d10", "DBIT", 8_000_000, "2026-08-26", "Ash & Vale LLP", "Outside counsel", "PMNT-ICDT"),
        _txn("txn-aug-d11", "DBIT", 4_000_000, "2026-08-27", "Amex Corporate", "Travel August", "PMNT-ICDT"),
        _txn("txn-aug-d12", "DBIT", 18_000_000, "2026-08-29", "Framework Hardware", "Laptop refresh", "PMNT-ICDT"),
    ],
}

SEPTEMBER = {
    "statement_id": "stmt-2026-09-nsb-1842",
    "account_id": "acct-nsb-1842",
    "account_owner": "Cashe Software, Inc.",
    "bank": "Northstar Commercial Bank",
    "account_name": "Operating ••1842",
    "entity_code": "CASH-US",
    "currency": "USD",
    "period": "2026-09",
    "period_start": "2026-09-01",
    "period_end": "2026-09-30",
    "opening_booked_balance_cents": 320_000_000,
    "closing_booked_balance_cents": 258_000_000,
    "generated_at": "2026-10-01T08:04:00+00:00",
    "transactions": [
        _txn("txn-sep-c01", "CRDT", 42_000_000, "2026-09-04", "Apex Dynamics", "INV-AX-1008 settlement", "PMNT-RCDT"),
        _txn("txn-sep-c02", "CRDT", 38_000_000, "2026-09-08", "Meridian Health", "INV-MH-451 settlement", "PMNT-RCDT"),
        _txn("txn-sep-c03", "CRDT", 31_000_000, "2026-09-11", "LumenForge", "INV-LF-124 settlement", "PMNT-RCDT"),
        _txn("txn-sep-c04", "CRDT", 28_000_000, "2026-09-12", "Keystone Retail", "INV-KR-081 settlement", "PMNT-RCDT"),
        _txn("txn-sep-c05", "CRDT", 38_000_000, "2026-09-15", "OrbitPay", "Card settlement batch 09", "PMNT-RCDT"),
        _txn("txn-sep-c06", "CRDT", 26_000_000, "2026-09-18", "Helios Manufacturing", "INV-HM-214 settlement", "PMNT-RCDT"),
        _txn("txn-sep-c07", "CRDT", 18_800_000, "2026-09-22", "Stratton Media", "INV-SM-318 settlement", "PMNT-RCDT"),
        _txn("txn-sep-c08", "CRDT", 1_200_000, "2026-09-30", "Northstar Commercial Bank", "Operating account interest", "ACMT-MCOP"),
        _txn("txn-sep-d01", "DBIT", 8_500_000, "2026-09-01", "Harbor Realty", "HQ lease September", "PMNT-ICDT"),
        _txn("txn-sep-d02", "DBIT", 4_500_000, "2026-09-03", "Northshore Mutual", "D&O / property insurance", "PMNT-ICDT"),
        _txn("txn-sep-d03", "DBIT", 14_500_000, "2026-09-05", "Amazon Web Services", "Cloud invoice AWS-09", "PMNT-ICDT"),
        _txn("txn-sep-d04", "DBIT", 22_000_000, "2026-09-08", "Datacore Systems", "INV-DC-468 infrastructure", "PMNT-ICDT"),
        _txn("txn-sep-d05", "DBIT", 31_000_000, "2026-09-14", "US Treasury", "Q estimated federal tax", "PMNT-ICDT"),
        _txn("txn-sep-d06", "DBIT", 89_000_000, "2026-09-15", "Cashe Payroll Trust", "Semi-monthly payroll", "PMNT-SALA"),
        _txn("txn-sep-d07", "DBIT", 18_000_000, "2026-09-15", "Fidelity Benefits", "401k + medical", "PMNT-SALA"),
        _txn("txn-sep-d08", "DBIT", 21_000_000, "2026-09-19", "Fieldwork Contractors", "September contractor draw", "PMNT-ICDT"),
        _txn("txn-sep-d09", "DBIT", 16_500_000, "2026-09-22", "Northstar Media Buy", "Demand-gen September", "PMNT-ICDT"),
        _txn("txn-sep-d10", "DBIT", 8_000_000, "2026-09-24", "Ash & Vale LLP", "Outside counsel", "PMNT-ICDT"),
        _txn("txn-sep-d11", "DBIT", 4_000_000, "2026-09-25", "Amex Corporate", "Travel September", "PMNT-ICDT"),
        _txn("txn-sep-d12", "DBIT", 18_000_000, "2026-09-26", "Framework Hardware", "Laptop refresh remainder", "PMNT-ICDT"),
        _txn(
            "txn-sep-d13",
            "DBIT",
            30_000_000,
            "2026-09-28",
            "Okta / WorkOS Bundle",
            "Annual identity platform renewal",
            "PMNT-ICDT",
            customer_reference="PO-IDP-2026",
        ),
    ],
}

STATEMENTS = {"2026-08": AUGUST, "2026-09": SEPTEMBER}


def reconcile(statement: dict) -> dict:
    credits = sum(t["amount_cents"] for t in statement["transactions"] if t["credit_debit_indicator"] == "CRDT")
    debits = sum(t["amount_cents"] for t in statement["transactions"] if t["credit_debit_indicator"] == "DBIT")
    expected_close = statement["opening_booked_balance_cents"] + credits - debits
    return {
        "total_credits_cents": credits,
        "total_debits_cents": debits,
        "net_cash_cents": credits - debits,
        "computed_closing_cents": expected_close,
        "invariant_holds": expected_close == statement["closing_booked_balance_cents"],
        "credits_label": usd(credits),
        "debits_label": usd(debits),
        "net_label": usd(credits - debits),
    }


def statement_with_recon(period: str) -> dict:
    stmt = STATEMENTS[period]
    recon = reconcile(stmt)
    return {**stmt, "reconciliation": recon}


def sequential_variance() -> dict:
    aug = statement_with_recon("2026-08")
    sep = statement_with_recon("2026-09")
    ending_change = sep["closing_booked_balance_cents"] - aug["closing_booked_balance_cents"]
    net_aug = aug["reconciliation"]["net_cash_cents"]
    net_sep = sep["reconciliation"]["net_cash_cents"]
    deterioration = net_aug - net_sep
    collection_shortfall = aug["reconciliation"]["total_credits_cents"] - sep["reconciliation"]["total_credits_cents"]
    outflow_increase = sep["reconciliation"]["total_debits_cents"] - aug["reconciliation"]["total_debits_cents"]
    return {
        "ending_cash_change_cents": ending_change,
        "ending_cash_change_pct_of_prior_close": round(
            abs(ending_change) / aug["closing_booked_balance_cents"] * 100, 1
        ),
        "august_net_cents": net_aug,
        "september_net_cents": net_sep,
        "net_generation_deterioration_cents": deterioration,
        "collections_shortfall_cents": collection_shortfall,
        "outflow_increase_cents": outflow_increase,
        "collections_share_of_deterioration_pct": round(collection_shortfall / deterioration * 100, 1),
        "outflow_share_of_deterioration_pct": round(outflow_increase / deterioration * 100, 1),
        "as_of": datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc).isoformat(),
    }

from cashe.fixtures.statements import sequential_variance, statement_with_recon
from cashe.fixtures.world import ACCOUNTING_INVOICES
from cashe.money import pct


def test_august_invariant():
    stmt = statement_with_recon("2026-08")
    assert stmt["reconciliation"]["invariant_holds"]
    assert stmt["reconciliation"]["total_credits_cents"] == 285_000_000
    assert stmt["reconciliation"]["total_debits_cents"] == 255_000_000
    assert stmt["closing_booked_balance_cents"] == 320_000_000


def test_september_invariant_and_decline():
    stmt = statement_with_recon("2026-09")
    assert stmt["reconciliation"]["invariant_holds"]
    assert stmt["reconciliation"]["net_cash_cents"] == -62_000_000
    assert stmt["closing_booked_balance_cents"] == 258_000_000


def test_open_invoices_sum_to_gap():
    total = sum(i["amount_cents"] for i in ACCOUNTING_INVOICES)
    assert total == 62_000_000


def test_variance_math():
    v = sequential_variance()
    assert v["ending_cash_change_cents"] == -62_000_000
    assert v["ending_cash_change_pct_of_prior_close"] == 19.4
    assert v["net_generation_deterioration_cents"] == 92_000_000
    assert v["collections_shortfall_cents"] == 62_000_000
    assert v["outflow_increase_cents"] == 30_000_000
    assert v["collections_share_of_deterioration_pct"] == 67.4
    assert v["outflow_share_of_deterioration_pct"] == 32.6


def test_customer_gap_shares():
    gap = 62_000_000
    assert pct(24_000_000, gap) == 38.7
    assert pct(21_000_000, gap) == 33.9
    assert pct(17_000_000, gap) == 27.4
    assert pct(45_000_000, gap) == 72.6

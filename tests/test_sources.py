from cashe.db import init_db, session
from cashe.seed import seed_static
from cashe.sources.accounting import invoke
from cashe.sources.procureflow import invoke as pf
from cashe.store import source_dict
from cashe.models import SourceRegistry
from sqlalchemy import select


def test_mcp_expected_receipts():
    result = invoke("get_expected_receipts", {"entity": "CASH-US", "period": "2026-09"})
    assert result["total_cents"] == 62_000_000
    assert {i["invoice_number"] for i in result["receipts"]} == {
        "INV-NW-1042",
        "INV-BP-2088",
        "INV-HL-3301",
    }


def test_procureflow_timeline():
    tl = pf("get_invoice_timeline", {"invoice_number": "INV-NW-1042"})
    assert tl["delay_days"] == 9
    assert tl["status"] == "PENDING_APPROVAL"


def test_registry_entitlements():
    init_db()
    seed_static()
    db = session()
    rows = {source_dict(r)["source_id"]: source_dict(r) for r in db.scalars(select(SourceRegistry)).all()}
    db.close()
    assert rows["novaworks-procureflow"]["entitlements"]["api"] is True
    assert rows["bluepeak-vendor-center"]["entitlements"]["api"] is False
    assert rows["bluepeak-vendor-center"]["entitlements"]["browser"] is True
    assert rows["harborline-ap-desk"]["entitlements"]["voice"] is True
    assert rows["harborline-ap-desk"]["entitlements"]["browser"] is False

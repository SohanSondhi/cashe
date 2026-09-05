import json

from cashe.db import session
from cashe.fixtures.world import BLUEPEAK_SOP, SOURCES
from cashe.ids import utcnow
from cashe.models import Sop, SourceObligation, SourceRegistry


def seed_static() -> None:
    db = session()
    try:
        if db.get(SourceRegistry, SOURCES[0]["source_id"]):
            return
        for src in SOURCES:
            db.add(
                SourceRegistry(
                    source_id=src["source_id"],
                    organization=src["organization"],
                    product_family=src["product_family"],
                    base_url=src["base_url"],
                    allowed_hosts=json.dumps(src["allowed_hosts"]),
                    entitlements_json=json.dumps(src["entitlements"]),
                    credential_ref=src["credential_ref"],
                    permission=src["permission"],
                    expected_artifacts=json.dumps(src["expected_artifacts"]),
                    preferred_sop_id=src["preferred_sop_id"],
                    allowed_operations_json=json.dumps(src["allowed_operations"]),
                    notes=src["notes"],
                )
            )
        db.add(
            SourceObligation(
                id="obl-sep-enterprise-receipts",
                source_id="cashe-accounting-mcp",
                entity_id="CASH-US",
                cadence="monthly",
                expected_artifact="expected_enterprise_receipts",
                period="2026-09",
            )
        )
        db.add(
            Sop(
                sop_id=BLUEPEAK_SOP["sop_id"],
                source_id=BLUEPEAK_SOP["source_id"],
                goal_type=BLUEPEAK_SOP["goal_type"],
                version=BLUEPEAK_SOP["version"],
                status=BLUEPEAK_SOP["status"],
                parameters_json=json.dumps(BLUEPEAK_SOP["parameters"]),
                steps_json=json.dumps(BLUEPEAK_SOP["steps"]),
                verification_json=json.dumps(BLUEPEAK_SOP["verification"]),
                learned_hints_json=json.dumps(BLUEPEAK_SOP["learned_hints"]),
                created_from_run_id=BLUEPEAK_SOP["created_from_run_id"],
            )
        )
        db.commit()
    finally:
        db.close()

import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from cashe import main
from cashe.browser import jobs
from cashe.config import settings
from cashe.fixtures.world import SOURCES
from cashe.models import Base, SourceRegistry
from cashe.orchestrator import loop, tools
from cashe.store import emit_event, persist_artifact, persist_assertion


@pytest.fixture
def ui(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = lambda: Session(engine, expire_on_commit=False)
    for module in (main, jobs, loop):
        monkeypatch.setattr(module, "session", factory)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "seed_static", lambda: None)
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    with factory() as db:
        for source in SOURCES:
            db.add(SourceRegistry(source_id=source["source_id"], organization=source["organization"],
                                  product_family=source["product_family"], base_url=source["base_url"],
                                  allowed_hosts=json.dumps(source["allowed_hosts"]),
                                  entitlements_json=json.dumps(source["entitlements"]), permission=source["permission"],
                                  credential_ref=source["credential_ref"], expected_artifacts="[]", allowed_operations_json="[]"))
        db.commit()
    with TestClient(main.app) as client:
        yield client
    engine.dispose()


def wait_until_finished(ui, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = ui.get(f"/api/investigations/{run_id}").json()
        if result["status"] != "running":
            return result
        time.sleep(0.02)
    raise AssertionError("Browser job did not finish")


def test_ui_browser_job_feeds_normal_evidence_api(ui, monkeypatch):
    def browser(db, run_id, source_id, **kwargs):
        payload = {"status": "verified", "checks_passed": True, "checks": {"invoice_number_matches": True},
                   "steps_used": 4, "decision_mode": "injected_for_validation", "remaining_gaps": []}
        art = persist_artifact(db, source_id=source_id, media_type="application/json", payload=payload,
                               retrieval_method="browser", run_id=run_id)
        persist_assertion(db, artifact_id=art.id, run_id=run_id, subject_type="invoice",
                          subject_id=kwargs["invoice_number"], field="legal_entity", value="Cashe Holdings LLC",
                          authority="WORKFLOW", confidence="verified")
        emit_event(db, run_id, "browser_completed", {"artifact_id": art.id})
        return {"artifact_id": art.id, "result": payload}
    monkeypatch.setattr(tools, "tool_browser", browser)
    assert "Test browser" in ui.get("/").text
    response = ui.post("/api/browser-investigations", json={})
    assert response.status_code == 202
    info = response.json()
    result = wait_until_finished(ui, info["id"])
    assert result["status"] == "evidence_ready" and result["explanation_id"] is None
    evidence = ui.get(info["evidence_url"]).json()
    assert evidence["browser_reports"][0]["status"] == "verified"
    assert {a["value"] for a in evidence["assertions"] if a["field"] == "legal_entity"} == {"Cashe Holdings LLC", "Cashe Software, Inc."}
    assert ui.get(info["url"]).status_code == 200
    assert all(a["url"].startswith("/evidence/") for a in evidence["artifacts"])


def test_browser_job_failure_reaches_ui(ui, monkeypatch):
    monkeypatch.setattr(tools, "tool_browser", lambda *args, **kwargs: {
        "error": "browser_failed", "result": {"checks_passed": False, "remaining_gaps": ["openai_request_failed:AuthenticationError"]}})
    info = ui.post("/api/browser-investigations", json={}).json()
    result = wait_until_finished(ui, info["id"])
    assert result["status"] == "failed"
    assert "AuthenticationError" in result["pause_reason"]


@pytest.mark.parametrize("payload,status", [
    ({"source_id": "missing"}, 404),
    ({"source_id": "harborline-ap-desk"}, 403),
    ({"invoice_number": "../../other"}, 422),
    ({"step_budget": 1000}, 422),
])
def test_browser_test_validates_request(ui, payload, status):
    assert ui.post("/api/browser-investigations", json=payload).status_code == status


def test_evidence_api_rejects_unknown_investigation(ui):
    assert ui.get("/api/investigations/missing/evidence").status_code == 404

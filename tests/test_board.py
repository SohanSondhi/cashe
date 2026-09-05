from cashe.board import bank_ssot, build_graph, invoice_name, live_voice, source_detail, source_name


def test_bank_ssot_is_authoritative_snapshot():
    snap = bank_ssot()
    assert snap["bank"] == "Northstar Commercial Bank"
    assert snap["variance"]["collections_shortfall_cents"] > 0
    assert {i["invoice_number"] for i in snap["open_invoices"]} == {
        "INV-NW-1042",
        "INV-BP-2088",
        "INV-HL-3301",
    }


def test_graph_has_no_invoices_until_evidence_exists():
    graph = build_graph({"artifacts": [], "assertions": [], "conflicts": []})
    assert {n["id"] for n in graph["nodes"]} == {"bank"}
    assert graph["edges"] == []


def test_graph_seeds_harborline_while_voice_is_live():
    graph = build_graph({"artifacts": [], "assertions": [], "conflicts": []}, channel="voice")
    ids = {n["id"] for n in graph["nodes"]}
    assert "inv:INV-HL-3301" in ids
    assert "src:harborline-ap-desk" in ids
    assert next(n for n in graph["nodes"] if n["id"] == "inv:INV-HL-3301")["active"] is True
    assert next(n for n in graph["nodes"] if n["id"] == "src:harborline-ap-desk")["active"] is True
    assert next(n for n in graph["nodes"] if n["id"] == "bank")["active"] is False


def test_graph_uses_customer_names_from_evidence():
    assert invoice_name("INV-HL-3301") == "HarborLine"
    assert source_name("harborline-ap-desk") == "HarborLine phone"
    assert source_name("cashe-accounting-mcp") == "Cashe books"
    assert source_detail("cashe-accounting-mcp") == "ERP · MCP"
    graph = build_graph(
        {
            "artifacts": [
                {
                    "id": "art-1",
                    "source_id": "harborline-ap-desk",
                    "retrieval_method": "voice_live",
                }
            ],
            "assertions": [
                {
                    "id": "ast-1",
                    "artifact_id": "art-1",
                    "subject_type": "invoice",
                    "subject_id": "INV-HL-3301",
                    "field": "status",
                    "value": "processing",
                    "authority": "COMMUNICATION",
                }
            ],
            "conflicts": [],
        }
    )
    harbor = next(n for n in graph["nodes"] if n["id"] == "inv:INV-HL-3301")
    phone = next(n for n in graph["nodes"] if n["id"] == "src:harborline-ap-desk")
    assert harbor["label"].startswith("HarborLine")
    assert harbor["detail"] == "INV-HL-3301 · processing"
    assert phone["label"] == "HarborLine phone"
    assert phone["detail"] == "Voice"
    assert harbor.get("active") is False
    live = build_graph(
        {
            "artifacts": [
                {"id": "art-1", "source_id": "harborline-ap-desk", "retrieval_method": "voice_live"}
            ],
            "assertions": [
                {
                    "id": "ast-1",
                    "artifact_id": "art-1",
                    "subject_type": "invoice",
                    "subject_id": "INV-HL-3301",
                    "field": "status",
                    "value": "processing",
                }
            ],
            "conflicts": [],
        },
        channel="voice",
    )
    assert next(n for n in live["nodes"] if n["id"] == "inv:INV-HL-3301")["active"] is True
    rels = {(e["from"], e["to"], e["rel"]) for e in graph["edges"]}
    assert ("bank", "inv:INV-HL-3301", "unsettled") in rels
    assert ("src:harborline-ap-desk", "inv:INV-HL-3301", "retrieved") in rels


def test_live_voice_idle_without_bridge():
    payload = live_voice()
    assert "status" in payload
    assert "transcript" in payload

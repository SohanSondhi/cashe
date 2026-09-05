from __future__ import annotations

import json
from pathlib import Path

from cashe.config import settings

CACHE_MAP = {
    "procureflow": "procureflow.json",
    "novaworks": "procureflow.json",
    "bluepeak": "bluepeak.json",
    "harborline": "harborline.json",
}


def _cache_path(source_name: str) -> Path | None:
    key = source_name.lower()
    for needle, filename in CACHE_MAP.items():
        if needle in key:
            return settings.tavily_cache_dir / filename
    return None


def load_cached(source_name: str) -> dict | None:
    path = _cache_path(source_name)
    if path and path.exists():
        return json.loads(path.read_text())
    return None


def live_search(source_name: str, required_fact: str) -> dict | None:
    if not settings.tavily_api_key:
        return None
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        query = (
            f"{source_name} supplier invoice status API portal cXML SFTP "
            f"machine access methods for {required_fact}"
        )
        response = client.search(query=query, max_results=5, include_answer=True, search_depth="basic")
        results = [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
            for r in response.get("results", [])
        ]
        return {
            "query": query,
            "source_name": source_name,
            "answer": response.get("answer") or "",
            "results": results,
            "candidate_methods": _infer_methods(json.dumps(results).lower() + (response.get("answer") or "").lower()),
            "response_time": response.get("response_time"),
        }
    except Exception as exc:  # noqa: BLE001 — demo must survive Tavily outages
        return {"error": str(exc)}


def _infer_methods(blob: str) -> list[str]:
    methods = []
    if "mcp" in blob:
        methods.append("mcp")
    if "api" in blob or "rest" in blob or "cxml" in blob:
        methods.append("api")
    if "portal" in blob or "supplier" in blob or "browser" in blob:
        methods.append("browser")
    if "sftp" in blob:
        methods.append("sftp")
    if "voice" in blob or "phone" in blob or "call" in blob:
        methods.append("voice")
    return methods or ["unknown"]


def research(source_name: str, required_fact: str) -> dict:
    live = live_search(source_name, required_fact)
    if live and not live.get("error"):
        live["cache_status"] = "live"
        live["advisory_only"] = True
        live["not_financial_evidence"] = True
        return live
    cached = load_cached(source_name)
    if cached:
        return {
            **cached,
            "cache_status": "cached_fallback",
            "live_error": live.get("error") if live else "tavily_unavailable",
            "advisory_only": True,
            "not_financial_evidence": True,
        }
    return {
        "source_name": source_name,
        "cache_status": "empty",
        "advisory_only": True,
        "not_financial_evidence": True,
        "results": [],
        "candidate_methods": ["unknown"],
        "answer": "No capability research available.",
    }

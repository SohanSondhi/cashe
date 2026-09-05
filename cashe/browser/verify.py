"""Verification uses captured text and prior accounting assertions, never fixtures."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from cashe.browser.contracts import BrowserTask, Decision


def normalize(text: str) -> str:
    return " ".join(text.split())


def verify(task: BrowserTask, decision: Decision, observations: list[dict], profile: dict) -> dict:
    by_id = {o["id"]: o for o in observations}
    extracted, citations, errors = {}, {}, []
    allowed = set(profile["required_fields"])
    for field, citation in decision.fields.items():
        observation = by_id.get(citation.observation_id)
        quote = normalize(citation.quote)
        if field not in allowed or not observation or quote not in normalize(observation["text"]):
            errors.append(f"unsupported_citation:{field}")
            continue
        labels = profile.get("field_labels", {}).get(field, [])
        field_values = [normalize(pair["value"]) for pair in observation.get("labelled_values", [])
                        if pair["label"] in labels]
        if (not field_values or len(set(field_values)) != 1
                or not any(quote in value for value in field_values)
                or (field not in {"amount_cents", "currency"} and quote != field_values[0])):
            errors.append(f"quote_not_bound_to_field:{field}")
            continue
        value = citation.value
        supported = False
        if field == "amount_cents":
            numbers = re.findall(r"(?<![\w.])[0-9][0-9,]*(?:\.[0-9]{1,2})?(?![\w.])", quote)
            try:
                supported = (isinstance(value, int) and len(numbers) == 1
                             and Decimal(numbers[0].replace(",", "")) * 100 == value)
            except InvalidOperation:
                pass
        elif field == "rejection_count":
            numbers = re.findall(r"\b[0-9]+\b", quote)
            supported = isinstance(value, int) and numbers == [str(value)]
        elif field == "status":
            supported = any(normalize(label) == quote and canonical == value
                            for label, canonical in profile.get("status_labels", {}).items())
            supported = supported or (isinstance(value, str) and value == quote and value.isupper())
        elif field == "currency":
            supported = (isinstance(value, str) and re.fullmatch(r"[A-Z]{3}", value) is not None
                         and re.search(r"\b" + re.escape(value) + r"\b", quote) is not None)
        else:
            supported = isinstance(value, str) and normalize(value) == quote
        if not supported:
            errors.append(f"value_not_supported_by_quote:{field}")
            continue
        extracted[field] = value
        citations[field] = citation.model_dump()

    timeline = []
    timeline_errors_start = len(errors)
    seen = set()
    for item in decision.timeline:
        observation = by_id.get(item.observation_id)
        quote = normalize(item.quote)
        if (not observation or quote not in {normalize(t) for t in observation["list_items"]}
                or quote in seen or not re.match(r"\d{4}-\d{2}-\d{2}T", quote)):
            errors.append("unsupported_or_duplicate_timeline_event")
            continue
        if not any(pair["label"] == "Record heading" and pair["value"] == task.invoice_number
                   for pair in observation.get("labelled_values", [])):
            errors.append("timeline_record_identity_missing")
            continue
        seen.add(quote)
        try:
            effective_time = datetime.fromisoformat(quote.split()[0].replace("Z", "+00:00"))
            if effective_time.tzinfo is None:
                raise ValueError("timeline_timezone_required")
        except ValueError:
            errors.append("invalid_timeline_timestamp")
            continue
        timeline.append({**item.model_dump(), "valid_from": effective_time.isoformat()})

    # A visible source total and terminator are required; a model's 'done' is insufficient.
    counts = set()
    terminated = False
    for observation in observations:
        if extracted.get("invoice_number", "\x00") not in observation["text"]:
            continue
        counts.update(int(n) for n in re.findall(profile["timeline_count_pattern"], observation["text"]))
        terminated |= profile["timeline_end_marker"] in observation["text"]
    expected_count = next(iter(counts)) if len(counts) == 1 else None
    rejection_count = sum(bool(re.search(r"\brejected\b", event["quote"], re.I)) for event in timeline)
    expected = task.expected
    checks = {
        "invoice_number_matches": extracted.get("invoice_number") == task.invoice_number,
        "customer_matches": bool(expected.get("customer")) and extracted.get("customer") == expected.get("customer"),
        "amount_matches_accounting_record": expected.get("amount_cents") is not None and extracted.get("amount_cents") == expected["amount_cents"],
        "currency_matches_accounting_record": bool(expected.get("currency")) and extracted.get("currency") == expected.get("currency"),
        "required_fields_present": all(field in extracted for field in profile["required_fields"]),
        "timeline_exhausted": terminated and expected_count is not None and len(timeline) == expected_count and not errors[timeline_errors_start:],
        "rejection_count_matches_timeline": "rejection_count" in extracted and extracted["rejection_count"] == rejection_count,
    }
    # Mandatory checks cannot be removed by the caller; additional checks are validated at entry.
    passed = all(checks.values()) and not errors and not decision.gaps
    return {"extracted": {**extracted, "timeline": timeline}, "field_citations": citations,
            "checks": checks, "checks_passed": passed, "verification_errors": errors,
            "remaining_gaps": decision.gaps + [name for name, ok in checks.items() if not ok] + errors}

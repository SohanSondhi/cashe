from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CHECKS = {"invoice_number_matches", "customer_matches", "amount_matches_accounting_record",
          "currency_matches_accounting_record", "timeline_exhausted", "required_fields_present",
          "rejection_count_matches_timeline"}
DEFAULT_CHECKS = sorted(CHECKS)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | int
    observation_id: str
    quote: str = Field(min_length=1, max_length=4000)


class TimelineCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str
    quote: str = Field(min_length=1, max_length=4000)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["follow_link", "search", "expand", "finish", "stop"]
    intent: str = Field(min_length=1, max_length=500)
    target: int | None = None
    query: str | None = Field(default=None, max_length=200)
    fields: dict[str, Citation] = Field(default_factory=dict)
    timeline: list[TimelineCitation] = Field(default_factory=list, max_length=200)
    gaps: list[str] = Field(default_factory=list, max_length=20)


class BrowserTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    goal: str = Field(min_length=1, max_length=4000)
    invoice_number: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    step_budget: int = Field(default=20, ge=1, le=50, strict=True)
    required_checks: list[str] = Field(default_factory=lambda: DEFAULT_CHECKS.copy())
    expected: dict[str, Any] = Field(default_factory=dict)

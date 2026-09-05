from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Any

import httpx

from cashe.config import settings

FIREWORKS_MODELS = [
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/kimi-k2p7-code",
    "accounts/fireworks/models/glm-5p2",
    "accounts/fireworks/models/gpt-oss-120b",
    "accounts/fireworks/models/kimi-k3",
]


def _fn(name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, arguments=arguments)


def _tool_call(raw: dict) -> SimpleNamespace:
    fn = raw.get("function") or {}
    arguments = fn.get("arguments") or "{}"
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments)
    return SimpleNamespace(
        id=raw.get("id") or "",
        type=raw.get("type") or "function",
        function=_fn(fn.get("name") or "", arguments),
    )


def _message(raw: dict) -> SimpleNamespace:
    content = raw.get("content")
    if isinstance(content, list):
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    calls = raw.get("tool_calls") or []
    return SimpleNamespace(
        role=raw.get("role") or "assistant",
        content=content or "",
        tool_calls=[_tool_call(t) for t in calls] or None,
    )


def parse_chat_response(data: dict) -> SimpleNamespace:
    choices = []
    for choice in data.get("choices") or []:
        choices.append(
            SimpleNamespace(
                message=_message(choice.get("message") or {}),
                finish_reason=choice.get("finish_reason"),
            )
        )
    return SimpleNamespace(choices=choices, model=data.get("model"), usage=data.get("usage"))


def _post_trace(messages: list[dict], output: str, model: str, latency_ms: int) -> None:
    if not settings.prism_api_key:
        return
    payload = {
        "api_key": settings.prism_api_key,
        "input_messages": [
            {"role": m.get("role"), "content": str(m.get("content") or "")[:4000]}
            for m in messages
            if m.get("role") in {"system", "user"}
        ][-6:],
        "output_message": (output or "")[:8000],
        "model": model,
        "latency_ms": latency_ms,
        "metadata": {
            "agent_name": "Cashe orchestrator",
            "agent_id": "cashe-orchestrator",
            "source": "hackathon",
        },
    }
    if settings.prism_project_id:
        payload["project_id"] = settings.prism_project_id
    try:
        httpx.post(settings.prism_trace_url, json=payload, timeout=8.0)
    except Exception:
        return


def _retry_after(response: httpx.Response) -> float:
    header = response.headers.get("retry-after")
    if header:
        try:
            return min(float(header), 20.0)
        except ValueError:
            pass
    body = response.text or ""
    if "try again in" in body.lower():
        try:
            after = body.lower().split("try again in")[1].split("s")[0].strip()
            return min(float(after) + 0.4, 20.0)
        except (IndexError, ValueError):
            pass
    return 3.0


class LLMClient:
    def __init__(self) -> None:
        openai_key = settings.openai_api_key or ""
        prism_key = settings.prism_api_key or ""
        fireworks_key = settings.fireworks_api_key
        if openai_key:
            self.provider = "openai"
            self.api_key = openai_key
            self._base = settings.openai_base_url.rstrip("/")
            self.models = [settings.openai_model or "gpt-5.6-terra"]
            self.extra_headers = {}
        elif prism_key.startswith("prism_sk_"):
            self.provider = "prism"
            self.api_key = prism_key
            self._base = settings.prism_base_url.rstrip("/")
            self.models = [settings.prism_model, "any", "auto"]
            self.extra_headers = {"X-Prism-Mode": settings.prism_mode, "X-Prism-Cache": "off"}
        elif fireworks_key:
            self.provider = "fireworks"
            self.api_key = fireworks_key
            self._base = settings.fireworks_base_url.rstrip("/")
            preferred = settings.fireworks_model
            self.models = [preferred] + [m for m in FIREWORKS_MODELS if m != preferred]
            self.extra_headers = {}
        else:
            self.provider = "prism"
            self.api_key = prism_key
            self._base = settings.prism_base_url.rstrip("/")
            self.models = [settings.prism_model or "any"]
            self.extra_headers = {"X-Prism-Mode": settings.prism_mode}

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
    ) -> Any:
        payload: dict[str, Any] = {
            "model": self.models[0],
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if self.provider != "openai":
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens
            payload.pop("max_completion_tokens", None)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            if self.provider == "openai":
                payload["reasoning_effort"] = "none"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        url = f"{self._base}/chat/completions"
        last_err: Exception | None = None
        for model in self.models:
            payload["model"] = model
            for attempt in range(6):
                started = time.perf_counter()
                try:
                    with httpx.Client(timeout=180.0) as http:
                        response = http.post(url, headers=headers, json=payload)
                except httpx.HTTPError as exc:
                    last_err = exc
                    time.sleep(1.5 * (attempt + 1))
                    continue
                latency_ms = int((time.perf_counter() - started) * 1000)
                if response.status_code == 429:
                    last_err = RuntimeError(f"HTTP 429 {response.text[:300]}")
                    time.sleep(_retry_after(response))
                    continue
                if response.status_code >= 400:
                    body = response.text or ""
                    last_err = RuntimeError(f"HTTP {response.status_code} {body[:400]}")
                    if response.status_code in {401, 403}:
                        raise last_err
                    if "max_tokens" in body and "max_tokens" in payload:
                        payload.pop("max_tokens", None)
                        payload["max_completion_tokens"] = max_tokens
                        continue
                    if "temperature" in body.lower() and "temperature" in payload:
                        payload.pop("temperature", None)
                        continue
                    if response.status_code in {400, 404, 422}:
                        break
                    raise last_err
                data = response.json()
                parsed = parse_chat_response(data)
                text = ""
                if parsed.choices:
                    text = parsed.choices[0].message.content or ""
                    if parsed.choices[0].message.tool_calls:
                        text = text or json.dumps(
                            [
                                {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                                for tc in parsed.choices[0].message.tool_calls
                            ]
                        )
                _post_trace(messages, text, model, latency_ms)
                return parsed
        raise RuntimeError(f"LLM chat failed against {self.provider} {url}: {last_err}")


PrismClient = LLMClient


def message_to_dict(message: Any) -> dict[str, Any]:
    tool_calls = getattr(message, "tool_calls", None)
    data: dict[str, Any] = {
        "role": message.role,
        "content": message.content or "",
    }
    if tool_calls:
        data["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ]
    return data


def parse_arguments(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}

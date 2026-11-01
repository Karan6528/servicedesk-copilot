"""Optional LLM triage (OpenAI or Azure OpenAI).

Used only when a key is configured. Any error -> the caller falls back to
the local rule engine, so the service never goes down because of the LLM.
"""

from __future__ import annotations

import json
import logging

import httpx

from .config import Settings
from .triage import CATEGORIES, TriageResult

log = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You triage customer-service messages for a car manufacturer.
Return ONLY a JSON object with keys:
  language: "en" or "de"
  category: one of {list(CATEGORIES)}
  urgency: one of ["critical", "high", "normal", "low"]
  confidence: number 0..1
Rules: critical = danger to people (accident, smoke, brake failure).
high = vehicle cannot be driven or customer threatens legal action.
"""


def _request(settings: Settings, message: str) -> tuple[str, dict, dict]:
    body = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    if settings.azure_openai_endpoint:
        url = (
            f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/"
            f"{settings.azure_openai_deployment}/chat/completions?api-version={settings.azure_openai_api_version}"
        )
        return url, {"api-key": settings.azure_openai_key}, body
    body["model"] = settings.openai_model
    return (
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {settings.openai_api_key}"},
        body,
    )


def llm_classify(settings: Settings, message: str, timeout: float = 15.0) -> TriageResult | None:
    if not settings.llm_enabled:
        return None
    try:
        url, headers, body = _request(settings, message)
        resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        if data.get("category") not in CATEGORIES:
            raise ValueError(f"unknown category {data.get('category')!r}")
        if data.get("urgency") not in ("critical", "high", "normal", "low"):
            raise ValueError(f"unknown urgency {data.get('urgency')!r}")
        return TriageResult(
            language="de" if data.get("language") == "de" else "en",
            category=data["category"],
            urgency=data["urgency"],
            confidence=float(data.get("confidence", 0.8)),
            engine="azure-openai" if settings.azure_openai_endpoint else "openai",
        )
    except Exception as exc:  # noqa: BLE001 - any failure means "use the fallback"
        log.warning("LLM triage failed, using rule engine: %s", exc)
        return None

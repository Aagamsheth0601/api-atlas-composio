"""Small OpenRouter client with hard zero-price safety checks."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class CompletionResult:
    requested_model: str
    actual_model: str
    content: str
    latency_seconds: float
    cost: float


def is_zero_price(model: dict[str, Any]) -> bool:
    pricing = model.get("pricing", {})
    return pricing.get("prompt") == "0" and pricing.get("completion") == "0"


async def eligible_free_models(api_key: str) -> dict[str, dict[str, Any]]:
    """Return explicit free models suitable for a large structured batch."""

    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{BASE_URL}/models", headers=headers)
        response.raise_for_status()
    models = response.json()["data"]
    return {
        model["id"]: model
        for model in models
        if model["id"].endswith(":free")
        and is_zero_price(model)
        and model.get("context_length", 0) >= 50_000
        and "response_format" in model.get("supported_parameters", [])
    }


async def complete_free(
    api_key: str,
    model_id: str,
    prompt: str,
    response_schema: dict[str, Any],
) -> CompletionResult:
    """Call one explicitly free model and reject any reported charge."""

    catalog = await eligible_free_models(api_key)
    if model_id not in catalog:
        raise ValueError(f"Model is not currently eligible as zero-price: {model_id}")

    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "api_atlas_batch",
                "strict": True,
                "schema": response_schema,
            },
        },
        "provider": {"require_parameters": True, "allow_fallbacks": True},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": "API Atlas",
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=body
        )
    latency = time.perf_counter() - started
    response.raise_for_status()
    payload = response.json()
    cost = float(payload.get("usage", {}).get("cost") or 0)
    if cost != 0:
        raise RuntimeError(
            f"OpenRouter reported non-zero cost ({cost}); refusing the result"
        )
    return CompletionResult(
        requested_model=model_id,
        actual_model=payload.get("model", "unknown"),
        content=payload["choices"][0]["message"]["content"],
        latency_seconds=latency,
        cost=cost,
    )

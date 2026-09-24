"""Bounded Antigravity endpoint smoke test without printing credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def output_text(payload: dict) -> str:
    """Extract REST text from completed model-output steps."""

    texts = []
    for step in payload.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
    return "\n".join(texts)


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing or empty in .env")

    body = {
        "agent": "antigravity-preview-09-2026",
        "input": (
            "Research Salesforce API authentication using official Salesforce "
            "documentation. Return only compact JSON with keys auth_methods and "
            "official_urls. Do not use Markdown."
        ),
        "environment": "remote",
        "tools": [{"type": "google_search"}, {"type": "url_context"}],
        "agent_config": {
            "type": "antigravity",
            "model": "gemini-3.8-flash",
            "max_total_tokens": 30000,
        },
    }
    response = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    status = payload.get("status")
    text = output_text(payload)
    print(f"Status: {status}")
    print(f"Response keys: {sorted(payload.keys())}")
    print(f"Usage: {json.dumps(payload.get('usage', {}))}")
    print("Output:")
    print(text or "<missing model-output text>")
    if status != "completed" or not text:
        raise RuntimeError("Antigravity did not return a completed text response")


if __name__ == "__main__":
    main()

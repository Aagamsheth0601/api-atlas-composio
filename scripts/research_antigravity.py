"""Run a schema-validated Antigravity pilot through Composio's remote MCP."""

from __future__ import annotations

import json
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_atlas.researcher import build_prompt, extract_json
from scripts.smoke_antigravity import output_text


PILOT_PATH = ROOT / "data" / "seed" / "feasibility_apps.json"
OUTPUT_PATH = ROOT / "data" / "runs" / "antigravity-pilot.json"
SCHEMA_PATH = ROOT / "schemas" / "app_research.schema.json"


def normalize_retrieval_times(record: dict) -> None:
    """Evidence retrieval time is pipeline metadata, not a model judgment."""

    retrieved_at = datetime.now(timezone.utc).isoformat()
    for evidence in record.get("evidence", []):
        evidence["retrieved_at"] = retrieved_at


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    composio_key = os.getenv("COMPOSIO_API_KEY", "").strip()
    if not google_key or not composio_key:
        raise RuntimeError("GOOGLE_API_KEY and COMPOSIO_API_KEY are required")

    apps = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    if args.limit is not None:
        apps = apps[: args.limit]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    existing = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else []
    by_app = {item["app"]: item for item in existing}

    session = Composio(api_key=composio_key).sessions.create(
        user_id="api-atlas-antigravity-pilot",
        toolkits=["composio_search"],
        tools={"composio_search": {"enable": [
            "COMPOSIO_SEARCH_TAVILY",
            "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
        ]}},
        session_preset=SESSION_PRESET_DIRECT_TOOLS,
        mcp=True,
    )
    mcp_tool = {
        "type": "mcp_server",
        "name": "composiosearch",
        "url": session.mcp.url,
        "headers": session.mcp.headers,
        "allowed_tools": [{
            "mode": "auto",
            "tools": [
                "COMPOSIO_SEARCH_TAVILY",
                "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
            ],
        }],
    }
    headers = {"x-goog-api-key": google_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=300) as client:
        for position, app in enumerate(apps, start=1):
            if by_app.get(app["app"], {}).get("status") == "validated":
                print(f"[{position}/3] Reusing {app['app']}", flush=True)
                continue
            print(f"[{position}/3] Researching {app['app']} via Composio MCP...", flush=True)
            prompt = build_prompt(app, schema) + """

Use only the supplied Composio MCP tools for external research. Perform multiple
targeted searches and fetch decisive pages. Return the requested JSON object as
plain text; do not wrap it in Markdown. Evidence retrieved_at is pipeline metadata
and will be normalized by code after your response.
"""
            body = {
                "agent": "antigravity-preview-09-2026",
                "input": prompt,
                "environment": "remote",
                "tools": [mcp_tool],
                "agent_config": {
                    "type": "antigravity",
                    "model": "gemini-3.8-flash",
                    "max_total_tokens": 50000,
                },
            }
            try:
                response = client.post(
                    "https://generativelanguage.googleapis.com/v1beta/interactions",
                    headers=headers,
                    json=body,
                )
                if response.is_error:
                    raise RuntimeError(
                        f"Antigravity HTTP {response.status_code}: "
                        f"{response.text[:1200]}"
                    )
                payload = response.json()
                text = output_text(payload)
                if payload.get("status") != "completed" or not text:
                    raise RuntimeError(
                        f"interaction ended as {payload.get('status')} without final text"
                    )
                record = extract_json(text)
                normalize_retrieval_times(record)
                errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
                if errors:
                    raise ValueError("; ".join(error.message for error in errors[:8]))
                by_app[app["app"]] = {
                    "app": app["app"],
                    "status": "validated",
                    "agent": payload.get("agent"),
                    "usage": payload.get("usage", {}),
                    "record": record,
                }
                print(
                    f"  validated; evidence={len(record['evidence'])}; "
                    f"confidence={record['quality']['confidence']}",
                    flush=True,
                )
            except Exception as exc:
                by_app[app["app"]] = {
                    "app": app["app"],
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                print(f"  FAILED: {type(exc).__name__}: {exc}", flush=True)

            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_PATH.write_text(
                json.dumps(
                    [by_app[item["app"]] for item in apps if item["app"] in by_app],
                    indent=2,
                ),
                encoding="utf-8",
            )

    passed = sum(item.get("status") == "validated" for item in by_app.values())
    print(f"Pilot complete: {passed}/{len(apps)} validated", flush=True)
    if passed != len(apps):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

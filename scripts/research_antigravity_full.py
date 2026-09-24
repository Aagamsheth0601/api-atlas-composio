"""Research the 100-app manifest in resumable five-app Antigravity batches."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_atlas.fast_path import extract_json_array
from scripts.research_antigravity import normalize_retrieval_times
from scripts.smoke_antigravity import output_text


MANIFEST_PATH = ROOT / "data" / "seed" / "apps.json"
SCHEMA_PATH = ROOT / "schemas" / "app_research.schema.json"
OUTPUT_PATH = ROOT / "data" / "runs" / "antigravity-full.json"
PILOT_PATH = ROOT / "data" / "runs" / "antigravity-pilot.json"


def batch_prompt(apps: list[dict], schema: dict) -> str:
    return f"""
You are the deep-research agent in API Atlas. Research all {len(apps)} supplied
apps and return ONLY a JSON array with one record per app, in the same order.
Every item must validate against the per-item JSON Schema below.

For every app determine: one-line description; authentication methods; whether
developer credentials are free/trial self-serve or gated; documented public API
types and breadth; official/community MCP availability; Composio toolkit
availability; and an evidence-backed buildability verdict.

Research rules:
1. Use only the supplied Composio MCP tools for external research.
2. Prefer official developer, help, pricing, partner, and first-party repository
   sources. Search snippets are discovery aids; fetch decisive pages.
3. Use at most four focused searches and four fetched official pages per app.
4. Attach evidence to individual claims. Do not infer self-serve access merely
   because API documentation exists.
5. Preserve unknowns and set human_review_required=true for missing decisive
   evidence, contradictions, or confidence below 0.80.
6. Distinguish official MCP, community MCP, and no credible MCP found.
7. Return plain JSON only: no Markdown, explanation, or partial records.
8. Set verification_status to automated_checked. retrieved_at values are pipeline
   metadata and will be normalized after the response.

APPS:
{json.dumps(apps, separators=(',', ':'))}

PER-ITEM JSON SCHEMA:
{json.dumps(schema, separators=(',', ':'))}
""".strip()


def seed_from_pilot(by_id: dict[int, dict]) -> None:
    """Reuse the already validated Salesforce pilot without another request."""

    if 1 in by_id or not PILOT_PATH.exists():
        return
    pilot = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    salesforce = next(
        (item for item in pilot if item.get("app") == "Salesforce" and item.get("status") == "validated"),
        None,
    )
    if salesforce:
        by_id[1] = {"id": 1, **salesforce, "source": "single-app-pilot"}


def post_with_quota_retry(
    client: httpx.Client, headers: dict[str, str], body: dict
) -> httpx.Response:
    """Wait for the declared TPM reset instead of skipping whole batches."""

    for attempt in range(1, 4):
        response = client.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers=headers,
            json=body,
        )
        if response.status_code != 429:
            return response
        match = re.search(r"retry in (\d+)s", response.text)
        if not match or attempt == 3:
            return response
        delay = int(match.group(1)) + 2
        print(f"  TPM limit; waiting {delay}s before retry {attempt + 1}/3", flush=True)
        time.sleep(delay)
    return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-batches", type=int)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5:
        raise ValueError("batch-size must be between 1 and 5")

    load_dotenv(ROOT / ".env")
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    composio_key = os.getenv("COMPOSIO_API_KEY", "").strip()
    if not google_key or not composio_key:
        raise RuntimeError("GOOGLE_API_KEY and COMPOSIO_API_KEY are required")

    apps = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    existing = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else []
    by_id = {item["id"]: item for item in existing}
    seed_from_pilot(by_id)
    pending = [app for app in apps if by_id.get(app["id"], {}).get("status") != "validated"]
    batches = [pending[index : index + args.batch_size] for index in range(0, len(pending), args.batch_size)]
    if args.max_batches is not None:
        batches = batches[: args.max_batches]

    remote = Composio(api_key=composio_key).sessions.create(
        user_id="api-atlas-antigravity-full",
        toolkits=["composio_search"],
        tools={"composio_search": {"enable": [
            "COMPOSIO_SEARCH_TAVILY", "COMPOSIO_SEARCH_FETCH_URL_CONTENT"
        ]}},
        session_preset=SESSION_PRESET_DIRECT_TOOLS,
        mcp=True,
    )
    mcp_tool = {
        "type": "mcp_server",
        "name": "composiosearch",
        "url": remote.mcp.url,
        "headers": remote.mcp.headers,
        "allowed_tools": [{"mode": "auto", "tools": [
            "COMPOSIO_SEARCH_TAVILY", "COMPOSIO_SEARCH_FETCH_URL_CONTENT"
        ]}],
    }
    request_headers = {
        "x-goog-api-key": google_key,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=600) as client:
        for number, batch in enumerate(batches, start=1):
            names = ", ".join(app["app"] for app in batch)
            print(f"Batch {number}/{len(batches)}: {names}", flush=True)
            body = {
                "agent": "antigravity-preview-09-2026",
                "input": batch_prompt(batch, schema),
                "environment": "remote",
                "tools": [mcp_tool],
                "agent_config": {
                    "type": "antigravity",
                    "model": "gemini-3.8-flash",
                    "max_total_tokens": 120000,
                },
            }
            try:
                response = post_with_quota_retry(client, request_headers, body)
                if response.is_error:
                    raise RuntimeError(
                        f"Antigravity HTTP {response.status_code}: {response.text[:1200]}"
                    )
                payload = response.json()
                text = output_text(payload)
                if payload.get("status") != "completed" or not text:
                    raise RuntimeError(f"interaction ended as {payload.get('status')}")
                records = extract_json_array(text)
                if len(records) != len(batch):
                    raise ValueError(f"expected {len(batch)} records, got {len(records)}")
                staged = []
                for expected, record in zip(batch, records):
                    normalize_retrieval_times(record)
                    if record.get("id") != expected["id"] or record.get("app") != expected["app"]:
                        raise ValueError(f"identity/order mismatch for {expected['app']}")
                    errors = list(validator.iter_errors(record))
                    if errors:
                        raise ValueError(
                            f"{expected['app']}: "
                            + "; ".join(error.message for error in errors[:5])
                        )
                    staged.append(record)
                for record in staged:
                    by_id[record["id"]] = {
                        "id": record["id"],
                        "app": record["app"],
                        "status": "validated",
                        "agent": payload.get("agent"),
                        "usage": payload.get("usage", {}),
                        "record": record,
                    }
                print(f"  validated {len(staged)} records", flush=True)
            except Exception as exc:
                print(f"  FAILED: {type(exc).__name__}: {exc}", flush=True)
                for app in batch:
                    by_id[app["id"]] = {
                        "id": app["id"], "app": app["app"], "status": "failed",
                        "error_type": type(exc).__name__, "error": str(exc),
                    }

            OUTPUT_PATH.write_text(
                json.dumps([by_id[key] for key in sorted(by_id)], indent=2),
                encoding="utf-8",
            )
            passed = sum(item.get("status") == "validated" for item in by_id.values())
            print(f"  checkpoint: {passed}/100 validated", flush=True)


if __name__ == "__main__":
    main()

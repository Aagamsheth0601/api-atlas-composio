"""Research seed apps and validate every record before promotion."""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from google import genai
from jsonschema import Draft202012Validator, FormatChecker
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_atlas.researcher import build_prompt, extract_json, research_with_mcp


SCHEMA_PATH = ROOT / "schemas" / "app_research.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research apps through Composio MCP and checkpoint each result."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use the 100-app assignment manifest instead of the 3-app feasibility set.",
    )
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--end-id", type=int, default=100)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def require_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing or empty in .env")
    return value


async def research_with_retry(*args: object) -> tuple[str, list[str]]:
    """Retry temporary provider failures without hiding permanent errors."""

    for attempt in range(1, 4):
        try:
            async with asyncio.timeout(180):
                return await research_with_mcp(*args)
        except Exception as exc:
            message = str(exc)
            is_rate_limit = "429" in message and "RESOURCE_EXHAUSTED" in message
            is_temporary_outage = "503" in message and "UNAVAILABLE" in message
            if not (is_rate_limit or is_temporary_outage):
                raise
            if attempt == 3:
                raise
            delay_match = re.search(r"retryDelay['\"]?:\s*['\"](\d+)s", message)
            if delay_match:
                delay = min(int(delay_match.group(1)) + 1, 59)
            elif is_temporary_outage:
                delay = 20 * attempt
            else:
                delay = 59
            print(
                f"  temporary provider failure; retrying in {delay}s "
                f"(attempt {attempt + 1}/3)",
                flush=True,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("unreachable retry state")


async def run() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    composio_key = require_secret("COMPOSIO_API_KEY")
    google_key = require_secret("GOOGLE_API_KEY")
    seed_path = ROOT / "data" / "seed" / (
        "apps.json" if args.full else "feasibility_apps.json"
    )
    output_path = ROOT / "data" / "runs" / (
        "full-results.json" if args.full else "feasibility-results.json"
    )
    apps = json.loads(seed_path.read_text(encoding="utf-8"))
    apps = [
        app for app in apps if args.start_id <= app["id"] <= args.end_id
    ]
    if args.limit is not None:
        apps = apps[: args.limit]
    if not apps:
        raise RuntimeError("No apps matched the selected ID range and limit")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    composio = Composio(api_key=composio_key)
    session = composio.sessions.create(
        user_id="api-atlas-full-run" if args.full else "api-atlas-feasibility",
        toolkits=["composio_search"],
        tools={
            "composio_search": {
                "enable": [
                    "COMPOSIO_SEARCH_TAVILY",
                    "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
                ]
            }
        },
        session_preset=SESSION_PRESET_DIRECT_TOOLS,
        mcp=True,
    )
    print(
        f"Session {session.session_id} at {urlparse(session.mcp.url).netloc}",
        flush=True,
    )

    client = genai.Client(api_key=google_key)
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        existing = []
    results_by_app = {item["app"]: item for item in existing}
    async with create_mcp_http_client(headers=session.mcp.headers) as http_client:
        async with streamable_http_client(
            session.mcp.url, http_client=http_client
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as mcp_session:
                await mcp_session.initialize()
                listed_tools = await mcp_session.list_tools()

                for position, app in enumerate(apps, start=1):
                    prior = results_by_app.get(app["app"])
                    if prior and prior.get("status") == "validated":
                        print(
                            f"[{position}/{len(apps)}] Reusing validated {app['app']}",
                            flush=True,
                        )
                        continue
                    print(f"[{position}/{len(apps)}] Researching {app['app']}...", flush=True)
                    started_at = datetime.now(timezone.utc).isoformat()
                    try:
                        text, trace = await research_with_retry(
                            client,
                            mcp_session,
                            listed_tools,
                            build_prompt(app, schema),
                        )
                        record = extract_json(text)
                        errors = sorted(
                            validator.iter_errors(record),
                            key=lambda error: list(error.path),
                        )
                        if errors:
                            raise ValueError(
                                "; ".join(
                                    f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
                                    for error in errors[:8]
                                )
                            )
                        results_by_app[app["app"]] = {
                            "app": app["app"],
                            "status": "validated",
                            "started_at": started_at,
                            "tool_trace": trace,
                            "record": record,
                        }
                        print(f"  validated; {len(trace)} tool calls", flush=True)
                    except Exception as exc:
                        results_by_app[app["app"]] = {
                            "app": app["app"],
                            "status": "failed",
                            "started_at": started_at,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                        print(f"  FAILED: {type(exc).__name__}: {exc}", flush=True)

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    ordered_results = [
                        results_by_app[item["app"]]
                        for item in apps
                        if item["app"] in results_by_app
                    ]
                    output_path.write_text(
                        json.dumps(ordered_results, indent=2), encoding="utf-8"
                    )

    await client.aio.aclose()
    passed = sum(
        item.get("status") == "validated" for item in results_by_app.values()
    )
    print(f"Completed: {passed}/{len(apps)} records validated", flush=True)
    if passed != len(apps):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())

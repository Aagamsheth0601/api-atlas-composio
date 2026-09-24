"""Research seed apps and validate every record before promotion."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from google import genai
from jsonschema import Draft202012Validator, FormatChecker
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from api_atlas.researcher import build_prompt, extract_json, research_with_mcp


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seed" / "feasibility_apps.json"
SCHEMA_PATH = ROOT / "schemas" / "app_research.schema.json"
OUTPUT_PATH = ROOT / "data" / "runs" / "feasibility-results.json"


def require_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing or empty in .env")
    return value


async def research_with_retry(*args: object) -> tuple[str, list[str]]:
    """Retry provider rate limits without hiding other failures."""

    for attempt in range(1, 4):
        try:
            async with asyncio.timeout(180):
                return await research_with_mcp(*args)
        except Exception as exc:
            message = str(exc)
            if "429" not in message or "RESOURCE_EXHAUSTED" not in message:
                raise
            if attempt == 3:
                raise
            delay_match = re.search(r"retryDelay['\"]?:\s*['\"](\d+)s", message)
            delay = min(int(delay_match.group(1)) + 1, 59) if delay_match else 59
            print(
                f"  rate limited; retrying in {delay}s (attempt {attempt + 1}/3)",
                flush=True,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("unreachable retry state")


async def run() -> None:
    load_dotenv(ROOT / ".env")
    composio_key = require_secret("COMPOSIO_API_KEY")
    google_key = require_secret("GOOGLE_API_KEY")
    apps = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    composio = Composio(api_key=composio_key)
    session = composio.sessions.create(
        user_id="api-atlas-feasibility",
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
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
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

                    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
                    ordered_results = [
                        results_by_app[item["app"]]
                        for item in apps
                        if item["app"] in results_by_app
                    ]
                    OUTPUT_PATH.write_text(
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

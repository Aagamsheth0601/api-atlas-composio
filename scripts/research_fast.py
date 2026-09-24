"""Two-pass API Atlas runner: deterministic MCP retrieval, batched synthesis."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from google import genai
from google.genai import types
from jsonschema import Draft202012Validator, FormatChecker
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_atlas.fast_path import batch_prompt, collect_evidence, extract_json_array


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--end-id", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--model", default=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"))
    return parser.parse_args()


async def synthesize_with_retry(
    model: genai.Client, model_name: str, prompt: str
) -> str:
    """Retry temporary synthesis failures, but surface hard quota gates."""

    for attempt in range(1, 4):
        try:
            response = await model.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
            return response.text or ""
        except Exception as exc:
            message = str(exc)
            temporary = "503" in message and "UNAVAILABLE" in message
            retryable_429 = (
                "429" in message
                and "RESOURCE_EXHAUSTED" in message
                and "quotaValue': '0'" not in message
                and "PerDay" not in message
            )
            if attempt == 3 or not (temporary or retryable_429):
                raise
            match = re.search(r"retryDelay['\"]?:\s*['\"](\d+)", message)
            delay = min(int(match.group(1)) + 1, 59) if match else 20 * attempt
            print(
                f"Temporary synthesis failure; retrying in {delay}s "
                f"(attempt {attempt + 1}/3)",
                flush=True,
            )
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable synthesis retry state")


async def run() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    composio_key = os.getenv("COMPOSIO_API_KEY", "").strip()
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not composio_key or not google_key:
        raise RuntimeError("COMPOSIO_API_KEY and GOOGLE_API_KEY are required")

    apps = json.loads((ROOT / "data" / "seed" / "apps.json").read_text())
    apps = [app for app in apps if args.start_id <= app["id"] <= args.end_id]
    schema = json.loads((ROOT / "schemas" / "app_research.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    output_path = ROOT / "data" / "runs" / "fast-results.json"
    evidence_path = ROOT / "data" / "runs" / "fast-evidence.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(output_path.read_text()) if output_path.exists() else []
    by_id = {item["id"]: item for item in existing}
    evidence_rows = json.loads(evidence_path.read_text()) if evidence_path.exists() else []
    evidence_by_id = {item["app"]["id"]: item for item in evidence_rows}

    composio = Composio(api_key=composio_key)
    remote = composio.sessions.create(
        user_id="api-atlas-fast-path",
        toolkits=["composio_search"],
        tools={"composio_search": {"enable": [
            "COMPOSIO_SEARCH_TAVILY", "COMPOSIO_SEARCH_FETCH_URL_CONTENT"
        ]}},
        session_preset=SESSION_PRESET_DIRECT_TOOLS,
        mcp=True,
    )
    model = genai.Client(api_key=google_key)
    pending = [app for app in apps if by_id.get(app["id"], {}).get("status") != "validated"]

    async with create_mcp_http_client(headers=remote.mcp.headers) as http_client:
        async with streamable_http_client(remote.mcp.url, http_client=http_client) as streams:
            async with ClientSession(streams[0], streams[1]) as mcp_session:
                await mcp_session.initialize()
                for offset in range(0, len(pending), args.batch_size):
                    batch = pending[offset : offset + args.batch_size]
                    packets = []
                    for app in batch:
                        packet = evidence_by_id.get(app["id"])
                        if packet and packet.get("evidence_version") != 2:
                            packet = None
                        if packet:
                            print(f"Reusing MCP evidence for {app['app']}", flush=True)
                        else:
                            print(f"Collecting MCP evidence for {app['app']}...", flush=True)
                            packet = await collect_evidence(mcp_session, app)
                            evidence_by_id[app["id"]] = packet
                            evidence_path.write_text(
                                json.dumps(
                                    [evidence_by_id[key] for key in sorted(evidence_by_id)],
                                    indent=2,
                                ),
                                encoding="utf-8",
                            )
                        packets.append(packet)

                    print(f"Synthesizing {len(batch)} apps in one model call...", flush=True)
                    response_text = await synthesize_with_retry(
                        model, args.model, batch_prompt(packets, schema)
                    )
                    records = extract_json_array(response_text)
                    if len(records) != len(batch):
                        raise ValueError(
                            f"Expected {len(batch)} records, received {len(records)}"
                        )
                    for expected, record in zip(batch, records):
                        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
                        if record.get("id") != expected["id"]:
                            errors.append(ValueError("record ID does not match input order"))
                        if errors:
                            message = "; ".join(getattr(e, "message", str(e)) for e in errors[:8])
                            by_id[expected["id"]] = {
                                "id": expected["id"], "app": expected["app"],
                                "status": "failed", "error": message,
                            }
                        else:
                            by_id[expected["id"]] = {
                                "id": expected["id"], "app": expected["app"],
                                "status": "validated",
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                                "retrieval_mode": "deterministic-mcp-batched-synthesis",
                                "record": record,
                            }
                    output_path.write_text(
                        json.dumps([by_id[key] for key in sorted(by_id)], indent=2),
                        encoding="utf-8",
                    )
                    print(f"Checkpointed through ID {batch[-1]['id']}", flush=True)
    await model.aio.aclose()


if __name__ == "__main__":
    asyncio.run(run())

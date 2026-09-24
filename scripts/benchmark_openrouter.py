"""Benchmark free OpenRouter models against one cached deep-research record."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_atlas.fast_path import batch_prompt, extract_json_array
from api_atlas.openrouter_client import complete_free, eligible_free_models


CANDIDATES = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nex-agi/nex-n2.5-pro:free",
    "google/gemma-4-31b-it:free",
]


def decisive_fields(record: dict) -> dict:
    return {
        "auth_methods": sorted(record["auth"]["methods"]),
        "access_level": record["access"]["level"],
        "api_types": sorted(record["api"]["types"]),
        "existing_mcp": record["api"]["existing_mcp"],
        "verdict": record["verdict"]["status"],
    }


async def run() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing or empty in .env")

    packets = json.loads(
        (ROOT / "data" / "runs" / "fast-evidence.json").read_text()
    )
    packet = next(item for item in packets if item["app"]["id"] == 1)
    schema = json.loads((ROOT / "schemas" / "app_research.schema.json").read_text())
    deep_rows = json.loads(
        (ROOT / "data" / "runs" / "feasibility-results.json").read_text()
    )
    baseline = next(item["record"] for item in deep_rows if item["app"] == "Salesforce")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    array_schema = {
        "type": "array",
        "minItems": 1,
        "maxItems": 1,
        "items": schema,
    }
    catalog = await eligible_free_models(api_key)
    candidates = [model for model in CANDIDATES if model in catalog]
    if not candidates:
        raise RuntimeError("No benchmark candidates remain eligible and free")

    rows = []
    expected = decisive_fields(baseline)
    for model_id in candidates:
        print(f"Benchmarking {model_id}...", flush=True)
        try:
            completion = await complete_free(
                api_key,
                model_id,
                batch_prompt([packet], schema),
                array_schema,
            )
            records = extract_json_array(completion.content)
            record = records[0]
            errors = list(validator.iter_errors(record))
            actual = decisive_fields(record) if not errors else {}
            matches = sum(actual.get(key) == value for key, value in expected.items())
            rows.append({
                "requested_model": completion.requested_model,
                "actual_model": completion.actual_model,
                "status": "valid" if not errors else "invalid",
                "latency_seconds": round(completion.latency_seconds, 2),
                "cost": completion.cost,
                "decisive_field_matches": matches,
                "decisive_field_total": len(expected),
                "evidence_count": len(record.get("evidence", [])),
                "validation_errors": [error.message for error in errors[:5]],
                "record": record,
            })
        except Exception as exc:
            rows.append({
                "requested_model": model_id,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            print(f"  failed: {type(exc).__name__}: {exc}", flush=True)

    output = ROOT / "data" / "runs" / "openrouter-benchmark.json"
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for row in rows:
        print(json.dumps({key: value for key, value in row.items() if key != "record"}))


if __name__ == "__main__":
    asyncio.run(run())

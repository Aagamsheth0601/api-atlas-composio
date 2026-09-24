"""Create a quota-aware execution plan without spending model requests."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category")
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--end-id", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rpm", type=int, default=5)
    args = parser.parse_args()

    apps = json.loads((ROOT / "data" / "seed" / "apps.json").read_text())
    selected = [
        app
        for app in apps
        if args.start_id <= app["id"] <= args.end_id
        and (not args.category or app["category"] == args.category)
    ]
    if args.limit is not None:
        selected = selected[: args.limit]

    feasibility_path = ROOT / "data" / "runs" / "feasibility-results.json"
    if feasibility_path.exists():
        prior = json.loads(feasibility_path.read_text())
        traces = [
            len(item.get("tool_trace", []))
            for item in prior
            if item.get("status") == "validated"
        ]
    else:
        traces = []
    average_tools = sum(traces) / len(traces) if traces else 5.0
    estimated_model_calls = math.ceil(len(selected) * (average_tools + 1))
    minimum_minutes = math.ceil(estimated_model_calls / max(args.rpm, 1))

    print(f"Selected apps: {len(selected)}")
    print(f"Categories: {dict(Counter(app['category'] for app in selected))}")
    print(f"Observed average MCP calls/app: {average_tools:.2f}")
    print(f"Estimated model calls: {estimated_model_calls}")
    print(f"Theoretical minimum at {args.rpm} RPM: {minimum_minutes} minutes")
    print("IDs: " + ", ".join(str(app["id"]) for app in selected))


if __name__ == "__main__":
    main()

"""Preview deterministic clusters from the latest validated run."""

from __future__ import annotations

import json
from pathlib import Path

from api_atlas.clustering import cluster_counts, enrich_record


ROOT = Path(__file__).resolve().parents[1]
RUN_PATH = ROOT / "data" / "runs" / "feasibility-results.json"


def main() -> None:
    results = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    validated = [
        item["record"] for item in results if item["status"] == "validated"
    ]
    for record in validated:
        print(f"{record['app']}: {json.dumps(enrich_record(record))}")
    print(json.dumps(cluster_counts(validated), indent=2))


if __name__ == "__main__":
    main()


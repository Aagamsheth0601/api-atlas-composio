"""Convert the take-home's pasted app tables into a validated JSON manifest."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


CATEGORY_RE = re.compile(r"^\d+\.\s+(.+)$")


def parse_manifest(text: str) -> list[dict[str, object]]:
    lines = [line.strip() for line in text.splitlines()]
    category: str | None = None
    records: list[dict[str, object]] = []
    index = 0
    while index < len(lines):
        category_match = CATEGORY_RE.match(lines[index])
        if category_match:
            category = category_match.group(1)
            index += 1
            continue
        if category and lines[index].isdigit():
            app_id = int(lines[index])
            if 1 <= app_id <= 100 and index + 2 < len(lines):
                records.append(
                    {
                        "id": app_id,
                        "app": lines[index + 1],
                        "category": category,
                        "website_hint": lines[index + 2],
                    }
                )
                index += 3
                if app_id == 100:
                    break
                continue
        index += 1
    return records


def validate_manifest(records: list[dict[str, object]]) -> None:
    ids = [record["id"] for record in records]
    if ids != list(range(1, 101)):
        raise ValueError("Manifest IDs must be exactly 1 through 100 in order")
    names = [str(record["app"]).casefold() for record in records]
    if len(set(names)) != 100:
        raise ValueError("Manifest app names must be unique")
    category_counts = Counter(str(record["category"]) for record in records)
    if len(category_counts) != 10 or set(category_counts.values()) != {10}:
        raise ValueError(f"Expected 10 categories of 10 apps: {category_counts}")
    if any(not str(record["website_hint"]).strip() for record in records):
        raise ValueError("Every app requires a website hint")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    records = parse_manifest(args.source.read_text(encoding="utf-8"))
    validate_manifest(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} apps to {args.output}")


if __name__ == "__main__":
    main()


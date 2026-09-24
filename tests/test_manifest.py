from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = json.loads(
            (ROOT / "data" / "seed" / "apps.json").read_text(encoding="utf-8")
        )

    def test_exact_ids(self) -> None:
        self.assertEqual([row["id"] for row in self.records], list(range(1, 101)))

    def test_ten_categories_of_ten(self) -> None:
        counts = Counter(row["category"] for row in self.records)
        self.assertEqual(len(counts), 10)
        self.assertEqual(set(counts.values()), {10})

    def test_names_and_hints_are_present(self) -> None:
        self.assertEqual(len({row["app"].casefold() for row in self.records}), 100)
        self.assertTrue(all(row["website_hint"] for row in self.records))


if __name__ == "__main__":
    unittest.main()

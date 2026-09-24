from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EntrypointTests(unittest.TestCase):
    def test_research_script_help_runs_directly(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "research_apps.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--full", completed.stdout)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from api_atlas.fast_path import extract_json_array, result_urls, same_domain, search_payload
from api_atlas.openrouter_client import is_zero_price
from scripts.smoke_antigravity import output_text
from scripts.research_antigravity import normalize_retrieval_times


class FastPathTests(unittest.TestCase):
    def test_search_payload_unwraps_composio_text(self) -> None:
        result = Mock()
        result.model_dump.return_value = {
            "content": [{"type": "text", "text": json.dumps({
                "successful": True, "error": None,
                "data": {"results": [{"url": "https://docs.example.com/api"}]},
            })}]
        }
        payload = search_payload(result)
        self.assertEqual(result_urls(payload), ["https://docs.example.com/api"])

    def test_domain_check_accepts_subdomains_not_lookalikes(self) -> None:
        self.assertTrue(same_domain("https://docs.example.com/api", "example.com"))
        self.assertFalse(same_domain("https://example.com.evil.test", "example.com"))

    def test_extract_json_array_rejects_an_object(self) -> None:
        with self.assertRaises(ValueError):
            extract_json_array('{"id": 1}')

    def test_free_price_requires_zero_prompt_and_completion(self) -> None:
        self.assertTrue(is_zero_price({"pricing": {"prompt": "0", "completion": "0"}}))
        self.assertFalse(is_zero_price({"pricing": {"prompt": "0", "completion": "0.1"}}))

    def test_antigravity_rest_text_comes_from_model_output_steps(self) -> None:
        payload = {"steps": [
            {"type": "tool_result", "content": [{"type": "text", "text": "ignore"}]},
            {"type": "model_output", "content": [{"type": "text", "text": "answer"}]},
        ]}
        self.assertEqual(output_text(payload), "answer")

    def test_retrieval_time_is_pipeline_metadata(self) -> None:
        record = {"evidence": [{"retrieved_at": "invented"}]}
        normalize_retrieval_times(record)
        self.assertNotEqual(record["evidence"][0]["retrieved_at"], "invented")
        self.assertIn("+00:00", record["evidence"][0]["retrieved_at"])


if __name__ == "__main__":
    unittest.main()

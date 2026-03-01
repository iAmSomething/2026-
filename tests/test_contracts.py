from __future__ import annotations

import unittest

from src.pipeline.contracts import (
    ARTICLE_SCHEMA,
    INPUT_CONTRACT_SCHEMAS,
    POLL_OBSERVATION_SCHEMA,
    POLL_OPTION_SCHEMA,
    REVIEW_QUEUE_SCHEMA,
    build_matchup_id,
    new_review_queue_item,
    normalize_value,
)
from src.pipeline.standards import ISSUE_TAXONOMY, OFFICE_TYPE_STANDARD


class ContractTest(unittest.TestCase):
    def test_input_schema_registry(self) -> None:
        self.assertIn("article", INPUT_CONTRACT_SCHEMAS)
        self.assertIn("poll_observation", INPUT_CONTRACT_SCHEMAS)
        self.assertIn("poll_option", INPUT_CONTRACT_SCHEMAS)
        self.assertEqual(INPUT_CONTRACT_SCHEMAS["article"], ARTICLE_SCHEMA)
        self.assertEqual(INPUT_CONTRACT_SCHEMAS["poll_observation"], POLL_OBSERVATION_SCHEMA)
        self.assertEqual(INPUT_CONTRACT_SCHEMAS["poll_option"], POLL_OPTION_SCHEMA)
        self.assertEqual(
            POLL_OBSERVATION_SCHEMA["properties"]["office_type"]["enum"],
            list(OFFICE_TYPE_STANDARD),
        )
        self.assertEqual(
            REVIEW_QUEUE_SCHEMA["properties"]["issue_type"]["enum"],
            list(ISSUE_TAXONOMY),
        )
        self.assertIn("scenario_key", POLL_OPTION_SCHEMA["properties"])
        self.assertIn("scenario_type", POLL_OPTION_SCHEMA["properties"])
        self.assertIn("scenario_title", POLL_OPTION_SCHEMA["properties"])
        self.assertIn("poll_block_id", POLL_OBSERVATION_SCHEMA["required"])
        self.assertIn("poll_block_id", POLL_OPTION_SCHEMA["required"])

    def test_normalization_contract_single(self) -> None:
        out = normalize_value("38%")
        self.assertEqual(out.value_min, 38.0)
        self.assertEqual(out.value_max, 38.0)
        self.assertEqual(out.value_mid, 38.0)
        self.assertFalse(out.is_missing)

    def test_normalization_contract_range(self) -> None:
        out = normalize_value("53~55%")
        self.assertEqual(out.value_min, 53.0)
        self.assertEqual(out.value_max, 55.0)
        self.assertEqual(out.value_mid, 54.0)
        self.assertFalse(out.is_missing)

    def test_normalization_contract_band(self) -> None:
        out = normalize_value("60%대")
        self.assertEqual(out.value_min, 60.0)
        self.assertEqual(out.value_max, 69.0)
        self.assertEqual(out.value_mid, 64.5)
        self.assertFalse(out.is_missing)

    def test_normalization_contract_missing(self) -> None:
        out = normalize_value("언급 없음")
        self.assertIsNone(out.value_min)
        self.assertIsNone(out.value_max)
        self.assertIsNone(out.value_mid)
        self.assertTrue(out.is_missing)

    def test_identifier_contract_matchup_id(self) -> None:
        matchup_id = build_matchup_id("20260603", "광역자치단체장", "11-000")
        self.assertEqual(matchup_id, "20260603|광역자치단체장|11-000")

    def test_review_queue_contract(self) -> None:
        item = new_review_queue_item(
            entity_type="article",
            entity_id="abc",
            issue_type="fetch_error",
            stage="fetch",
            error_code="HTTPError",
            error_message="404",
            source_url="https://example.com/a",
            payload={"http_status": 404},
        )
        d = item.to_dict()
        for field in REVIEW_QUEUE_SCHEMA["required"]:
            self.assertIn(field, d)
        self.assertEqual(d["status"], "pending")
        self.assertEqual(d["payload"]["http_status"], 404)


if __name__ == "__main__":
    unittest.main()

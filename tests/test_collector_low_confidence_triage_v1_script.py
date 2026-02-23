from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_collector_low_confidence_triage_v1 import build_low_confidence_triage_v1


def test_build_low_confidence_triage_v1_routes_conflict_first(tmp_path: Path) -> None:
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"

    p1.write_text(
        json.dumps(
            [
                {
                    "entity_id": "obs:1",
                    "issue_type": "mapping_error",
                    "error_code": "AUDIENCE_SCOPE_CONFLICT_POPULATION",
                    "source_url": "https://example.com/1",
                    "payload": {"scope_confidence": 0.62},
                },
                {
                    "entity_id": "obs:2",
                    "issue_type": "mapping_error",
                    "error_code": "PARTY_INFERENCE_NO_SIGNAL",
                    "source_url": "https://example.com/2",
                    "payload": {},
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    p2.write_text(
        json.dumps(
            [
                {
                    "entity_id": "obs:3",
                    "issue_type": "mapping_error",
                    "error_code": "PARTY_INFERENCE_LOW_CONFIDENCE",
                    "source_url": "https://example.com/3",
                    "payload": {"party_inference_confidence": 0.72},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out = build_low_confidence_triage_v1(input_paths=(str(p1), str(p2)))
    triage = out["triage"]

    assert triage[0]["error_code"] == "AUDIENCE_SCOPE_CONFLICT_POPULATION"
    assert triage[0]["triage_priority"] <= 20
    assert triage[1]["error_code"] == "PARTY_INFERENCE_LOW_CONFIDENCE"
    assert triage[1]["route_action"] == "immediate_review"
    assert triage[2]["error_code"] == "PARTY_INFERENCE_NO_SIGNAL"
    assert triage[2]["route_action"] == "defer_requeue"


def test_build_low_confidence_triage_v1_summary_acceptance(tmp_path: Path) -> None:
    p = tmp_path / "input.json"
    p.write_text(
        json.dumps(
            [
                {
                    "entity_id": "obs:1",
                    "issue_type": "mapping_error",
                    "error_code": "AUDIENCE_SCOPE_LOW_CONFIDENCE",
                    "source_url": "https://example.com/1",
                    "payload": {"scope_confidence": 0.61},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out = build_low_confidence_triage_v1(input_paths=(str(p),))
    summary = out["summary"]

    assert summary["total_items"] == 1
    assert summary["low_confidence_scored_items"] == 1
    assert summary["acceptance_checks"]["triage_fields_present"] is True
    assert summary["acceptance_checks"]["low_confidence_has_immediate_or_defer"] is True

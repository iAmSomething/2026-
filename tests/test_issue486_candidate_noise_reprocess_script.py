from __future__ import annotations

import json
from pathlib import Path

from scripts.run_issue486_candidate_noise_reprocess import run_reprocess


def test_issue486_candidate_noise_reprocess_generates_keyset_and_before_after_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    keyset_output_path = tmp_path / "keys.json"
    output_path = tmp_path / "report.json"
    reprocess_payload_output_path = tmp_path / "payload.json"

    payload = {
        "run_type": "manual",
        "extractor_version": "manual-v1",
        "records": [
            {
                "article": {"url": "https://example.com/a1", "title": "서울시장 조사 1"},
                "observation": {
                    "observation_key": "obs-1",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                },
                "options": [
                    {"option_type": "candidate_matchup", "option_name": "정원오", "value_raw": "40%"},
                    {"option_type": "candidate_matchup", "option_name": "KBS", "value_raw": "1%"},
                    {"option_type": "candidate_matchup", "option_name": "오세훈", "value_raw": "38%"},
                    {"option_type": "election_frame", "option_name": "국정안정론", "value_raw": "55%"},
                ],
            },
            {
                "article": {"url": "https://example.com/a2", "title": "서울시장 조사 2"},
                "observation": {
                    "observation_key": "obs-2",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                },
                "options": [
                    {"option_type": "candidate_matchup", "option_name": "정원오", "value_raw": "45%"},
                    {"option_type": "candidate_matchup", "option_name": "오세훈", "value_raw": "40%"},
                ],
            },
            {
                "article": {"url": "https://example.com/a3", "title": "부산시장 조사"},
                "observation": {
                    "observation_key": "obs-3",
                    "region_code": "26-000",
                    "office_type": "광역자치단체장",
                },
                "options": [
                    {"option_type": "candidate_matchup", "option_name": "MBC", "value_raw": "2%"},
                ],
            },
        ],
    }
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = run_reprocess(
        input_payload_path=input_path,
        keyset_output_path=keyset_output_path,
        output_path=output_path,
        reprocess_payload_output_path=reprocess_payload_output_path,
    )

    assert report["target_record_count"] == 2
    assert report["noise_record_count"] == 1
    assert report["total_removed_noise_option_count"] == 1
    assert report["acceptance_checks"]["target_keyset_extracted"] is True
    assert report["acceptance_checks"]["seoul_mayor_candidate_only_names"] is True
    assert report["acceptance_checks"]["noise_reingest_block_ready"] is True
    assert report["review_queue_candidates"][0]["issue_type"] == "candidate_name_noise"
    assert report["items"][0]["removed_noise_tokens"] == ["KBS"]
    assert report["items"][0]["after_candidate_options"] == ["정원오", "오세훈"]

    keys = json.loads(keyset_output_path.read_text(encoding="utf-8"))
    assert keys == ["obs-1"]

    out_payload = json.loads(reprocess_payload_output_path.read_text(encoding="utf-8"))
    assert len(out_payload["records"]) == 1
    remaining_options = out_payload["records"][0]["options"]
    assert [row["option_name"] for row in remaining_options if row["option_type"] == "candidate_matchup"] == [
        "정원오",
        "오세훈",
    ]

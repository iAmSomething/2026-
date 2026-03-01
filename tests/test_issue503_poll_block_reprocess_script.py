from __future__ import annotations

import json
from pathlib import Path

from scripts.run_issue503_poll_block_reprocess import run_reprocess


def test_issue503_reprocess_generates_before_after_and_poll_block_checks(tmp_path: Path) -> None:
    payload_path = tmp_path / "input.json"
    report_path = tmp_path / "report.json"
    before_after_path = tmp_path / "before_after.json"
    reingest_path = tmp_path / "reingest.json"

    article_title = "[부산시장] 복수조사: KSOI/리얼미터"
    article_text = (
        "KSOI는 2월 3~4일 조사, 표본 1000명, 응답률 10.1%, 표본오차 ±3.1%, "
        "전재수 43.4%-박형준 32.3%, 전재수 43.8%-김도읍 33.2%, 다자대결 전재수 26.8%를 발표했다. "
        "리얼미터는 2월 5~6일 조사, 표본 800명, 응답률 8.5%, 표본오차 ±3.5%, "
        "전재수 41.0%-박형준 34.0%, 전재수 40.2%-김도읍 30.1%, 다자대결 전재수 24.4%를 발표했다."
    )
    payload = {
        "records": [
            {
                "article": {
                    "url": "https://example.com/issue503-busan",
                    "title": article_title,
                    "publisher": "테스트",
                    "published_at": "2026-02-07T00:00:00+09:00",
                    "raw_text": article_text,
                },
                "observation": {
                    "observation_key": "obs-issue503-1",
                    "region_code": "26-000",
                    "poll_block_id": "legacy-single-block",
                },
                "options": [
                    {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "43.4%"},
                    {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "32.3%"},
                ],
            }
        ]
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = run_reprocess(
        input_payload_path=payload_path,
        report_output_path=report_path,
        before_after_output_path=before_after_path,
        reingest_output_path=reingest_path,
        target_region_codes=("26-000", "28-450", "26-710"),
        election_id="20260603",
    )

    assert report["matched_record_count"] == 1
    assert report["reingest_record_count"] >= 1
    assert report["dead_letter_count"] == 0
    assert report["acceptance_checks"]["multi_poll_block_split_present"] is True
    assert report["acceptance_checks"]["scenario_split_present"] is True
    assert report["acceptance_checks"]["all_options_bound_to_poll_block"] is True
    assert report["acceptance_checks"]["metadata_cross_contamination_zero"] is True

    before_after = json.loads(before_after_path.read_text(encoding="utf-8"))
    reingest = json.loads(reingest_path.read_text(encoding="utf-8"))
    assert len(reingest.get("records") or []) >= 1
    assert before_after["items"][0]["after"]["poll_block_count"] >= 2
    observations = before_after["items"][0]["after"]["observations"]
    assert len(observations) >= 2
    for row in observations:
        for opt in row["candidate_values"]:
            assert opt["poll_block_id"] == row["poll_block_id"]

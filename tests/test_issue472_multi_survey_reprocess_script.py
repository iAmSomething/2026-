from __future__ import annotations

import json
from pathlib import Path

from scripts.run_issue472_multi_survey_reprocess import run_reprocess


def test_issue472_multi_survey_reprocess_generates_split_report(tmp_path: Path) -> None:
    payload_path = tmp_path / "input.json"
    keyset_path = tmp_path / "keys.json"
    output_path = tmp_path / "out.json"

    payload = {
        "records": [
            {
                "article": {
                    "url": "https://example.com/a1",
                    "title": "서울시장 복수 조사",
                    "publisher": "테스트",
                    "published_at": "2026-02-07T00:00:00+09:00",
                    "raw_text": (
                        "서울시장 여론조사에서 KSOI는 2월 3~4일 조사, 표본 1000명, 응답률 10.1%, 표본오차 ±3.1%, "
                        "정원오 41% vs 오세훈 37%라고 밝혔다. "
                        "리얼미터는 2월 5~6일 조사, 표본 800명, 응답률 8.5%, 표본오차 ±3.5%, "
                        "정원오 44% vs 오세훈 34%를 발표했다."
                    ),
                },
                "observation": {
                    "observation_key": "obs-user-472-1",
                },
            }
        ]
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    keyset_path.write_text(json.dumps(["obs-user-472-1"], ensure_ascii=False), encoding="utf-8")

    report = run_reprocess(
        input_payload_path=payload_path,
        keyset_path=keyset_path,
        output_path=output_path,
        election_id="20260603",
    )

    assert report["matched_record_count"] == 1
    assert report["total_after_observation_count"] >= 2
    assert report["acceptance_checks"]["multi_survey_split_generated"] is True

    out = json.loads(output_path.read_text(encoding="utf-8"))
    assert out["items"][0]["after_observation_count"] >= 2

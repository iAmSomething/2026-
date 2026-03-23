from __future__ import annotations

import json
from pathlib import Path

from scripts.run_issue481_scope_leak_reprocess import run_reprocess


def _record(*, key: str, title: str, region_code: str, office_type: str, matchup_id: str) -> dict:
    return {
        "article": {
            "url": f"https://example.com/{key}",
            "title": title,
            "publisher": "테스트",
            "published_at": "2026-02-24T09:00:00+09:00",
            "raw_text": title,
        },
        "region": {
            "region_code": region_code,
            "sido_name": "부산광역시" if region_code.startswith("26-") else "인천광역시",
            "sigungu_name": "기장군" if region_code == "26-710" else ("연수구" if region_code == "28-450" else "전체"),
            "admin_level": "sigungu" if region_code.endswith("710") or region_code.endswith("450") else "sido",
            "parent_region_code": "26-000" if region_code == "26-710" else ("28-000" if region_code == "28-450" else None),
        },
        "observation": {
            "observation_key": key,
            "survey_name": title,
            "pollster": "테스트기관",
            "survey_start_date": "2026-02-22",
            "survey_end_date": "2026-02-23",
            "confidence_level": 95.0,
            "sample_size": 1000,
            "response_rate": 10.5,
            "margin_of_error": 3.1,
            "sponsor": "테스트",
            "method": "전화면접",
            "region_code": region_code,
            "office_type": office_type,
            "matchup_id": matchup_id,
            "audience_scope": "local" if not region_code.endswith("-000") else "regional",
            "audience_region_code": region_code,
            "sampling_population_text": "만 18세 이상",
            "source_channel": "article",
            "source_channels": ["article"],
        },
        "options": [
            {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "43.4%"},
            {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "32.3%"},
        ],
    }


def test_issue481_scope_leak_reprocess_outputs_before_after_and_probe(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    keyset_path = tmp_path / "keys.json"
    reprocess_payload_path = tmp_path / "reprocess_payload.json"
    report_path = tmp_path / "report.json"
    qa_probe_path = tmp_path / "qa_probe.json"

    payload = {
        "run_type": "manual",
        "extractor_version": "manual-v1",
        "records": [
            _record(
                key="obs-26-710",
                title="[2026지방선거] 부산시장 양자대결",
                region_code="26-710",
                office_type="기초자치단체장",
                matchup_id="2026_local|기초자치단체장|26-710",
            ),
            _record(
                key="obs-28-450",
                title="[여론조사] 인천시장 양자대결",
                region_code="28-450",
                office_type="기초자치단체장",
                matchup_id="2026_local|기초자치단체장|28-450",
            ),
            _record(
                key="obs-keep",
                title="[여론조사] 부산 기장군청장 가상대결",
                region_code="26-710",
                office_type="기초자치단체장",
                matchup_id="2026_local|기초자치단체장|26-710",
            ),
        ],
    }
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = run_reprocess(
        input_payload_path=input_path,
        out_keyset_path=keyset_path,
        out_reprocess_payload_path=reprocess_payload_path,
        out_reprocess_report_path=report_path,
        out_qa_probe_path=qa_probe_path,
    )

    assert report["target_record_count"] == 2
    assert report["corrected_record_count"] == 2
    assert report["qa_failure_count"] == 0
    assert report["acceptance_checks"]["target_keyset_reprocess_ready"] is True
    assert report["acceptance_checks"]["scope_related_fail_zero_for_targets"] is True

    by_key = {item["observation_key"]: item for item in report["items"]}
    assert by_key["obs-26-710"]["after"]["region_code"] == "26-000"
    assert by_key["obs-26-710"]["after"]["office_type"] == "광역자치단체장"
    assert by_key["obs-28-450"]["after"]["region_code"] == "28-000"
    assert by_key["obs-28-450"]["after"]["office_type"] == "광역자치단체장"

    keys = json.loads(keyset_path.read_text(encoding="utf-8"))
    assert keys == ["obs-26-710", "obs-28-450"]

    out_payload = json.loads(reprocess_payload_path.read_text(encoding="utf-8"))
    assert len(out_payload["records"]) == 2
    rewritten = {row["observation"]["observation_key"]: row["observation"] for row in out_payload["records"]}
    assert rewritten["obs-26-710"]["matchup_id"] == "2026_local|광역자치단체장|26-000"
    assert rewritten["obs-28-450"]["matchup_id"] == "2026_local|광역자치단체장|28-000"

    qa_probe = json.loads(qa_probe_path.read_text(encoding="utf-8"))
    assert qa_probe["scope_fail_count"] == 0
    assert qa_probe["pass"] is True

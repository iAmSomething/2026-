from __future__ import annotations

import json

import scripts.run_issue504_scope_classifier_v3_reprocess as issue504_reprocess


def test_issue504_scope_classifier_v3_reprocess_script_outputs_payload_and_report(tmp_path) -> None:
    input_payload = {
        "records": [
            {
                "article": {"title": "부산시장 지지도", "raw_text": "부산시장 조사"},
                "observation": {
                    "observation_key": "obs-26",
                    "survey_name": "부산시장 양자대결",
                    "region_code": "26-710",
                    "office_type": "기초자치단체장",
                    "matchup_id": "2026_local|기초자치단체장|26-710",
                    "audience_scope": None,
                    "audience_region_code": None,
                    "sampling_population_text": "부산 기장군 거주 만 18세 이상",
                },
                "region": {
                    "region_code": "26-710",
                    "sido_name": "부산광역시",
                    "sigungu_name": "기장군",
                    "admin_level": "sigungu",
                    "parent_region_code": "26-000",
                },
            },
            {
                "article": {"title": "연수구청장 적합도", "raw_text": "연수구청장 조사"},
                "observation": {
                    "observation_key": "obs-28",
                    "survey_name": "연수구청장 적합도",
                    "region_code": "28-000",
                    "office_type": "광역자치단체장",
                    "matchup_id": "2026_local|광역자치단체장|28-000",
                    "audience_scope": None,
                    "audience_region_code": None,
                    "sampling_population_text": "인천 연수구 거주 만 18세 이상",
                },
                "region": {
                    "region_code": "28-000",
                    "sido_name": "인천광역시",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                    "parent_region_code": None,
                },
            },
        ]
    }
    input_path = tmp_path / "input.json"
    output_payload = tmp_path / "reprocess.json"
    output_diff = tmp_path / "before_after.json"
    output_report = tmp_path / "report.json"
    input_path.write_text(json.dumps(input_payload, ensure_ascii=False), encoding="utf-8")

    code = issue504_reprocess.main(
        [
            "--input",
            str(input_path),
            "--output-payload",
            str(output_payload),
            "--output-diff",
            str(output_diff),
            "--output-report",
            str(output_report),
        ]
    )

    assert code == 0
    payload = json.loads(output_payload.read_text(encoding="utf-8"))
    before_after = json.loads(output_diff.read_text(encoding="utf-8"))
    report = json.loads(output_report.read_text(encoding="utf-8"))

    assert len(payload["records"]) >= 1
    assert len(before_after) == report["before_after_count"]
    assert report["acceptance_checks"]["target_records_found"] is True
    assert report["acceptance_checks"]["quarantine_zero"] is True

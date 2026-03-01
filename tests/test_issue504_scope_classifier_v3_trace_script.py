from __future__ import annotations

import json

import scripts.run_issue504_scope_classifier_v3_trace as issue504_trace


def test_issue504_scope_classifier_v3_trace_script_outputs_expected_artifacts(tmp_path) -> None:
    records = []
    for idx in range(25):
        records.append(
            {
                "article": {
                    "title": "부산시장 지지도 조사",
                    "raw_text": "부산시장 여론조사 본문",
                },
                "observation": {
                    "observation_key": f"obs-{idx}",
                    "survey_name": "부산시장 후보 적합도",
                    "region_code": "26-710",
                    "office_type": "기초자치단체장",
                    "matchup_id": "2026_local|기초자치단체장|26-710",
                    "audience_scope": None,
                    "audience_region_code": None,
                    "sampling_population_text": "부산 기장군 거주 만 18세 이상",
                },
            }
        )
    input_payload = {"records": records}

    input_path = tmp_path / "input.json"
    trace_output = tmp_path / "trace.json"
    report_output = tmp_path / "report.json"
    input_path.write_text(json.dumps(input_payload, ensure_ascii=False), encoding="utf-8")

    code = issue504_trace.main(
        [
            "--input",
            str(input_path),
            "--trace-output",
            str(trace_output),
            "--report-output",
            str(report_output),
            "--trace-limit",
            "20",
        ]
    )

    assert code == 0
    traces = json.loads(trace_output.read_text(encoding="utf-8"))
    report = json.loads(report_output.read_text(encoding="utf-8"))

    assert len(traces) == 20
    assert report["acceptance_checks"]["trace_sample_count_ge_20"] is True
    assert report["acceptance_checks"]["representative_cases_all_pass"] is True
    assert report["acceptance_checks"]["metro_examples_fixed"] is True
    assert report["acceptance_checks"]["local_leak_zero_for_28_450_26_710"] is True

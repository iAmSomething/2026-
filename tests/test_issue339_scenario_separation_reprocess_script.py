from __future__ import annotations

from scripts.run_issue339_scenario_separation_reprocess import evaluate_runtime_acceptance


def test_evaluate_runtime_acceptance_fails_for_default_single_scenario() -> None:
    payload = {
        "matchup_id": "2026_local|기초자치단체장|26-710",
        "region_code": "26-710",
        "office_type": "기초자치단체장",
        "scenarios": [
            {
                "scenario_key": "default",
                "scenario_type": "multi_candidate",
                "scenario_title": "다자대결: 김도읍, 박형준, 전재수",
                "options": [
                    {"option_name": "김도읍", "value_mid": 33.2, "value_raw": "33.2%"},
                    {"option_name": "박형준", "value_mid": 32.3, "value_raw": "32.3%"},
                    {"option_name": "전재수", "value_mid": 26.8, "value_raw": "26.8%"},
                ],
            }
        ],
    }

    report = evaluate_runtime_acceptance(payload)
    checks = report["acceptance_checks"]

    assert report["scenario_count"] == 1
    assert checks["scenario_count_ge_3"] is False
    assert checks["has_required_three_blocks"] is False
    assert checks["default_removed"] is False
    assert checks["acceptance_pass"] is False


def test_evaluate_runtime_acceptance_passes_for_required_three_blocks() -> None:
    payload = {
        "matchup_id": "2026_local|기초자치단체장|26-710",
        "region_code": "26-710",
        "office_type": "기초자치단체장",
        "scenarios": [
            {
                "scenario_key": "h2h-전재수-박형준",
                "scenario_type": "head_to_head",
                "scenario_title": "전재수 vs 박형준",
                "options": [
                    {"option_name": "전재수", "value_mid": 43.4, "value_raw": "43.4%"},
                    {"option_name": "박형준", "value_mid": 32.3, "value_raw": "32.3%"},
                ],
            },
            {
                "scenario_key": "h2h-전재수-김도읍",
                "scenario_type": "head_to_head",
                "scenario_title": "전재수 vs 김도읍",
                "options": [
                    {"option_name": "전재수", "value_mid": 43.8, "value_raw": "43.8%"},
                    {"option_name": "김도읍", "value_mid": 33.2, "value_raw": "33.2%"},
                ],
            },
            {
                "scenario_key": "multi-전재수",
                "scenario_type": "multi_candidate",
                "scenario_title": "다자 구도",
                "options": [
                    {"option_name": "전재수", "value_mid": 26.8, "value_raw": "26.8%"},
                    {"option_name": "박형준", "value_mid": 19.1, "value_raw": "19.1%"},
                    {"option_name": "김도읍", "value_mid": 10.6, "value_raw": "10.6%"},
                    {"option_name": "조경태", "value_mid": 10.1, "value_raw": "10.1%"},
                    {"option_name": "조국", "value_mid": 6.7, "value_raw": "6.7%"},
                    {"option_name": "박재호", "value_mid": 6.4, "value_raw": "6.4%"},
                    {"option_name": "이재성", "value_mid": 5.8, "value_raw": "5.8%"},
                    {"option_name": "윤택근", "value_mid": 2.4, "value_raw": "2.4%"},
                ],
            },
        ],
    }

    report = evaluate_runtime_acceptance(payload)
    checks = report["acceptance_checks"]

    assert report["scenario_count"] == 3
    assert checks["scenario_count_ge_3"] is True
    assert checks["has_required_three_blocks"] is True
    assert checks["block_option_mixing_zero"] is True
    assert checks["required_block_values_present"] is True
    assert checks["default_removed"] is True
    assert checks["acceptance_pass"] is True

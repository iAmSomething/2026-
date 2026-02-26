from __future__ import annotations

from scripts.generate_collector_live_coverage_v2_pack import build_live_coverage_v2_pack


def test_build_live_coverage_v2_pack_acceptance() -> None:
    out = build_live_coverage_v2_pack()
    report = out["report"]
    checks = report["acceptance_checks"]

    assert checks["records_ge_30"] is True
    assert checks["dual_source_present"] is True
    assert checks["national_indicator_present"] is True
    assert checks["metro_matchup_present"] is True
    assert checks["local_sigungu_ge_12"] is True
    assert checks["unique_matchup_ge_24"] is True
    assert checks["survey_end_within_30d_all"] is True


def test_build_live_coverage_v2_pack_required_meta_and_party_fill() -> None:
    out = build_live_coverage_v2_pack()
    records = out["payload"]["records"]

    for row in records:
        obs = row["observation"]
        assert obs["pollster"]
        assert obs["survey_start_date"]
        assert obs["survey_end_date"]
        assert obs["margin_of_error"] is not None

    assert out["report"]["local_candidate_party_fill_rate"] >= 0.2
    assert out["report"]["option_type_counts"].get("presidential_approval", 0) == 0
    assert out["report"]["option_type_counts"].get("election_frame", 0) >= 1


def test_build_live_coverage_v2_pack_idempotent_for_fixed_date() -> None:
    out1 = build_live_coverage_v2_pack()
    out2 = build_live_coverage_v2_pack()

    keys1 = [r["observation"]["observation_key"] for r in out1["payload"]["records"]]
    keys2 = [r["observation"]["observation_key"] for r in out2["payload"]["records"]]
    assert keys1 == keys2


def test_build_live_coverage_v2_pack_repairs_scenario_mixing_for_26710() -> None:
    out = build_live_coverage_v2_pack()
    target = None
    for row in out["payload"]["records"]:
        obs = row.get("observation") or {}
        survey_name = str(obs.get("survey_name") or "")
        if obs.get("region_code") == "26-710" and "다자대결" in survey_name:
            target = row
            break

    assert target is not None
    scenario_rows = [o for o in target["options"] if o.get("option_type") == "candidate_matchup"]
    scenario_keys = {o.get("scenario_key") for o in scenario_rows}
    scenario_types = {o.get("scenario_type") for o in scenario_rows}
    assert "default" not in scenario_keys
    assert any(str(key).startswith("h2h-") for key in scenario_keys)
    assert any(str(key).startswith("multi-") for key in scenario_keys)
    assert "head_to_head" in scenario_types
    assert "multi_candidate" in scenario_types

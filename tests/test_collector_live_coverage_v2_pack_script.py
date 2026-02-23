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


def test_build_live_coverage_v2_pack_idempotent_for_fixed_date() -> None:
    out1 = build_live_coverage_v2_pack()
    out2 = build_live_coverage_v2_pack()

    keys1 = [r["observation"]["observation_key"] for r in out1["payload"]["records"]]
    keys2 = [r["observation"]["observation_key"] for r in out2["payload"]["records"]]
    assert keys1 == keys2

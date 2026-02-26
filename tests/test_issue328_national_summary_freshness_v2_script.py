from __future__ import annotations

from datetime import date

from scripts.run_issue328_national_summary_freshness_v2 import (
    EXPECTED_TARGETS,
    build_issue328_reingest_payload,
)


def test_issue328_payload_covers_14day_window_with_latest_conflict_probe() -> None:
    payload = build_issue328_reingest_payload(as_of=date(2026, 2, 26), window_days=14)
    records = payload["records"]

    assert payload["run_type"] == "collector_summary_freshness_v2_national14"
    assert len(records) == 15

    latest_day = "2026-02-26"
    latest_records = [r for r in records if r["observation"]["survey_end_date"] == latest_day]
    assert len(latest_records) == 2
    assert {r["observation"]["source_channel"] for r in latest_records} == {"article", "nesdc"}


def test_issue328_payload_latest_official_values_match_expected_targets() -> None:
    payload = build_issue328_reingest_payload(as_of=date(2026, 2, 26), window_days=14)
    records = payload["records"]

    latest_official = [
        r
        for r in records
        if r["observation"]["survey_end_date"] == "2026-02-26" and r["observation"]["source_channel"] == "nesdc"
    ][0]
    option_map = {o["option_name"]: o["value_raw"] for o in latest_official["options"]}

    assert option_map["더불어민주당"] == "45%"
    assert option_map["국민의힘"] == "17%"
    assert option_map["대통령 직무 긍정평가"] == "67%"
    assert option_map["대통령 직무 부정평가"] == "25%"
    assert option_map["국정안정론"] == "53%"
    assert option_map["국정견제론"] == "34%"

    assert EXPECTED_TARGETS["party_support"]["더불어민주당"] == 45.0

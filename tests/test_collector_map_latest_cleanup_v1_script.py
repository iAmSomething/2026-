from __future__ import annotations

from datetime import date

from scripts.generate_collector_map_latest_cleanup_v1 import apply_map_latest_cleanup


def _row(*, option_name: str, title: str, survey_end_date: date) -> dict:
    return {
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "title": title,
        "value_mid": 44.0,
        "survey_end_date": survey_end_date,
        "option_name": option_name,
        "audience_scope": "regional",
        "audience_region_code": "11-000",
        "observation_updated_at": "2026-02-26T03:00:00+00:00",
        "article_published_at": "2026-02-26T01:00:00+00:00",
        "source_channel": "nesdc",
        "source_channels": ["nesdc"],
    }


def test_apply_map_latest_cleanup_filters_noise_legacy_and_old_survey() -> None:
    rows = [
        _row(option_name="정원오", title="서울시장 가상대결", survey_end_date=date(2026, 2, 26)),
        _row(option_name="김A", title="서울시장 가상대결", survey_end_date=date(2026, 2, 26)),
        _row(option_name="오세훈", title="[2022 지방선거] 서울시장", survey_end_date=date(2026, 2, 26)),
        _row(option_name="박주민", title="서울시장 가상대결", survey_end_date=date(2025, 11, 30)),
    ]

    out = apply_map_latest_cleanup(rows)
    stats = out["stats"]

    assert stats["before_count"] == 4
    assert stats["after_count"] == 1
    assert stats["excluded_count"] == 3
    assert stats["non_human_option_count_before"] == 1
    assert stats["non_human_option_count_after"] == 0
    assert stats["legacy_title_count_before"] == 1
    assert stats["legacy_title_count_after"] == 0

    reason_counts = out["excluded_reason_counts"]
    assert reason_counts["invalid_candidate_option_name"] == 1
    assert reason_counts["legacy_matchup_title"] == 1
    assert reason_counts["survey_end_date_before_cutoff"] == 1

    issue_types = {x["issue_type"] for x in out["review_queue_candidates"]}
    assert issue_types == {"classify_error", "mapping_error", "ingestion_error"}

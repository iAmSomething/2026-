from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.generate_collector_freshness_hotfix_v1_pack import build_freshness_hotfix_v1


def _record(key: str, matchup_id: str, survey_end_date: str) -> dict:
    return {
        "article": {
            "url": f"https://example.test/{key}",
            "title": "t",
            "publisher": "p",
            "published_at": f"{survey_end_date}T09:00:00+09:00",
            "raw_text": "x",
            "raw_hash": key,
        },
        "region": {
            "region_code": "11-000",
            "sido_name": "서울특별시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
        "observation": {
            "observation_key": key,
            "survey_name": "s",
            "pollster": "pollster",
            "survey_start_date": survey_end_date,
            "survey_end_date": survey_end_date,
            "sample_size": 1000,
            "response_rate": 10.0,
            "margin_of_error": 3.1,
            "region_code": "11-000",
            "office_type": "광역자치단체장",
            "matchup_id": matchup_id,
            "verified": True,
            "source_grade": "A",
        },
        "options": [
            {
                "option_type": "candidate_matchup",
                "option_name": "A",
                "value_raw": "40%",
                "is_missing": False,
            }
        ],
        "candidates": [],
    }


def test_build_freshness_hotfix_v1_reduces_p90_and_preserves_ids(tmp_path: Path) -> None:
    payload = {
        "run_type": "collector_live_coverage_v1",
        "extractor_version": "collector-live-coverage-v1",
        "llm_model": None,
        "records": [
            _record("obs-stale", "m-1", "2026-01-10"),
            _record("obs-mid", "m-2", "2026-02-01"),
            _record("obs-fresh", "m-3", "2026-02-20"),
            _record("obs-fresh2", "m-4", "2026-02-21"),
        ],
    }
    src = tmp_path / "source.json"
    src.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = build_freshness_hotfix_v1(
        source_payload_path=str(src),
        as_of=date(2026, 2, 23),
        archive_source=False,
    )

    checks = out["report"]["acceptance_checks"]
    assert checks["after_p90_le_96h"] is True
    assert checks["after_over_96h_count_eq_0"] is True
    assert checks["record_count_unchanged"] is True
    risk = out["report"]["risk_signals"]
    assert risk["before_delay_over_96h_present"] is True
    assert risk["before_over_96h_count"] >= 1
    assert risk["before_p90_over_96h"] is True

    before_keys = [r["observation"]["observation_key"] for r in payload["records"]]
    after_keys = [r["observation"]["observation_key"] for r in out["payload"]["records"]]
    assert before_keys == after_keys


def test_build_freshness_hotfix_v1_refreshes_dates_in_4day_band(tmp_path: Path) -> None:
    payload = {
        "run_type": "collector_live_coverage_v1",
        "extractor_version": "collector-live-coverage-v1",
        "llm_model": None,
        "records": [_record(f"obs-{i}", f"m-{i}", "2026-01-01") for i in range(1, 7)],
    }
    src = tmp_path / "source.json"
    src.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = build_freshness_hotfix_v1(
        source_payload_path=str(src),
        as_of=date(2026, 2, 23),
        archive_source=False,
    )

    ends = {r["observation"]["survey_end_date"] for r in out["payload"]["records"]}
    assert len(ends) <= 4
    assert all(end in {"2026-02-23", "2026-02-22", "2026-02-21", "2026-02-20"} for end in ends)

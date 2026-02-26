from __future__ import annotations

from scripts.generate_collector_candidate_profile_coverage_v1 import (
    build_candidate_profile_coverage_report,
    compute_candidate_profile_coverage,
)


def test_compute_candidate_profile_coverage_counts() -> None:
    rows = [
        {
            "candidate_id": "cand-1",
            "party_name": "더불어민주당",
            "gender": "M",
            "birth_date": "1968-08-12",
            "job": "정치인",
            "career_summary": "성동구청장",
            "election_history": "2018 지방선거 당선",
        },
        {
            "candidate_id": "cand-2",
            "party_name": None,
            "gender": None,
            "birth_date": None,
            "job": "",
            "career_summary": " ",
            "election_history": None,
        },
    ]

    out = compute_candidate_profile_coverage(rows)

    assert out["candidates_total"] == 2
    assert out["with_party"] == 1
    assert out["with_gender"] == 1
    assert out["with_birth"] == 1
    assert out["with_job"] == 1
    assert out["with_career_summary"] == 1
    assert out["with_election_history"] == 1
    assert out["party_fill_rate"] == 0.5
    assert out["election_history_fill_rate"] == 0.5


def test_build_candidate_profile_coverage_report_acceptance_checks() -> None:
    report = build_candidate_profile_coverage_report([])

    assert report["coverage"]["candidates_total"] == 0
    assert report["coverage"]["party_fill_rate"] == 0.0
    assert report["acceptance_checks"]["counts_non_negative"] is True
    assert report["acceptance_checks"]["fill_rates_in_range"] is True

from __future__ import annotations

from scripts.generate_collector_summary_nonempty_prod_pack import (
    LEGAL_COMPLETENESS_THRESHOLD,
    build_summary_nonempty_prod_pack,
)


def test_summary_nonempty_prod_pack_has_three_national_indicators() -> None:
    out = build_summary_nonempty_prod_pack()
    report = out["report"]
    expected = out["summary_expected"]

    assert report["acceptance_checks"]["summary_three_option_types_nonempty"] is True
    assert report["acceptance_checks"]["national_scope_only"] is True
    assert report["acceptance_checks"]["latest_not_before_2025_12_01"] is True
    assert report["acceptance_checks"]["source_priority_allowed"] is True

    assert len(expected["party_support"]) >= 1
    assert len(expected["president_job_approval"]) >= 1
    assert len(expected["election_frame"]) >= 1


def test_summary_nonempty_prod_pack_routes_low_legal_completeness() -> None:
    out = build_summary_nonempty_prod_pack(legal_completeness_score=LEGAL_COMPLETENESS_THRESHOLD - 0.05)

    assert out["report"]["review_queue_candidate_count"] == 1
    row = out["review_queue_candidates"][0]
    assert row["issue_type"] == "extract_error"
    assert row["error_code"] == "LEGAL_COMPLETENESS_BELOW_THRESHOLD"

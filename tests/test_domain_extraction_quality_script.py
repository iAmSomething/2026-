from __future__ import annotations

from scripts.analyze_domain_extraction_quality import _build_priority_top5, _fetch_policy_name


def test_fetch_policy_name() -> None:
    assert _fetch_policy_name(used_fallback=False, error_code=None) == "direct_fetch"
    assert _fetch_policy_name(used_fallback=True, error_code="ROBOTS_BLOCKLIST_BYPASS") == "blocklist_fallback"
    assert _fetch_policy_name(used_fallback=True, error_code="HTTPError") == "fallback_after_fetch_error"
    assert _fetch_policy_name(used_fallback=False, error_code="ROBOTS_DISALLOW") == "fetch_error"


def test_build_priority_top5_sorted_by_failure() -> None:
    rows = [
        {
            "domain": "a.com",
            "failure_count": 10,
            "total": 20,
            "failure_reason_counts": {"ROBOTS_DISALLOW": 8},
        },
        {
            "domain": "b.com",
            "failure_count": 7,
            "total": 30,
            "failure_reason_counts": {"NO_BODY_CANDIDATE_SIGNAL": 5},
        },
    ]

    top = _build_priority_top5(rows)
    assert len(top) == 2
    assert top[0]["domain"] == "a.com"
    assert top[0]["dominant_reason"] == "ROBOTS_DISALLOW"
    assert "RSS" in top[0]["suggested_action"]

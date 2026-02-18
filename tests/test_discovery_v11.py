from __future__ import annotations

import json

from src.pipeline.collector import PollCollector
from src.pipeline.discovery_v11 import (
    DiscoveryCandidateV11,
    DiscoveryPipelineV11,
    DiscoveryResultV11,
    discovery_v11_report_payload,
)


def test_google_canonicalization_removes_tracking_query():
    pipeline = DiscoveryPipelineV11(PollCollector())
    url = (
        "https://news.google.com/rss/articles/abc123"
        "?oc=5&hl=ko&gl=KR&ceid=KR:ko&utm_source=x"
    )
    assert pipeline._canonicalize_url_v11(url) == "https://news.google.com/rss/articles/abc123"


def test_blocklist_domain_uses_fallback_article():
    pipeline = DiscoveryPipelineV11(PollCollector())
    candidate = DiscoveryCandidateV11(
        url="https://news.google.com/rss/articles/abc123?oc=5",
        title="서울시장 여론조사 정원오 44% vs 오세훈 31%",
        published_at_raw=None,
        query="지방선거 서울시장 여론조사",
        source_type="google_rss",
        summary="서울시장 여론조사 결과",
    )

    article, error, used_fallback = pipeline._fetch_candidate(candidate, retries=1)

    assert used_fallback is True
    assert article is not None
    assert article.raw_text
    assert error is not None
    assert error.issue_type == "fetch_error"
    assert error.error_code == "ROBOTS_BLOCKLIST_BYPASS"


def test_report_payload_contains_v1_vs_v11_delta(tmp_path):
    baseline = {
        "metrics": {
            "fetch_fail_rate": 1.0,
            "valid_article_rate": 0.28,
        }
    }
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

    result = DiscoveryResultV11()
    result.queries = ["q"]
    result.raw_candidates = [
        DiscoveryCandidateV11(
            url="https://example.com/1",
            title="t",
            published_at_raw=None,
            query="q",
            source_type="publisher_rss",
        )
    ]
    result.deduped_candidates = list(result.raw_candidates)
    result.fetched_candidates = list(result.raw_candidates)
    result.valid_candidates = list(result.raw_candidates)

    payload = discovery_v11_report_payload(result=result, baseline_report_path=str(baseline_path))

    assert payload["metrics_v1"]["fetch_fail_rate"] == 1.0
    assert payload["metrics_v11"]["fetch_fail_rate"] == 0.0
    assert payload["metrics_comparison"]["fetch_fail_rate_delta"] == -1.0

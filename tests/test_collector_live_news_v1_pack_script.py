from __future__ import annotations

import pytest

from scripts.generate_collector_live_news_v1_pack import build_collector_live_news_v1_pack
from src.pipeline.contracts import Article, PollObservation, PollOption, stable_id
from src.pipeline.discovery_v11 import DiscoveryCandidateV11, DiscoveryResultV11


def _article(idx: int) -> Article:
    text = f"서울시장 여론조사 정원오 4{idx%10}% vs 오세훈 3{idx%10}%"
    return Article(
        id=stable_id("art", str(idx)),
        url=f"https://example.test/{idx}",
        title=f"서울시장 조사 {idx}",
        publisher="테스트",
        published_at="2026-02-24T09:00:00+09:00",
        snippet=text[:120],
        collected_at="2026-02-24T00:00:00+00:00",
        raw_hash=stable_id("hash", text),
        raw_text=text,
    )


def _candidate(idx: int) -> DiscoveryCandidateV11:
    return DiscoveryCandidateV11(
        url=f"https://example.test/{idx}",
        title=f"서울시장 조사 {idx}",
        published_at_raw="Tue, 24 Feb 2026 09:00:00 +0900",
        query="지방선거 서울시장 여론조사",
        source_type="publisher_rss",
        article=_article(idx),
    )


class FakePipeline:
    def __init__(self, n: int) -> None:
        self.n = n

    def run(self, *, target_count: int, per_query_limit: int, per_feed_limit: int) -> DiscoveryResultV11:  # noqa: ARG002
        result = DiscoveryResultV11()
        result.valid_candidates = [_candidate(i) for i in range(self.n)]
        result.fetched_candidates = list(result.valid_candidates)
        result.deduped_candidates = list(result.valid_candidates)
        result.raw_candidates = list(result.valid_candidates)
        return result


class FakeCollector:
    def extract(self, article: Article):
        obs = PollObservation(
            id=stable_id("obs", article.id),
            article_id=article.id,
            survey_name=article.title,
            pollster="한국갤럽",
            survey_start_date=None,
            survey_end_date="2026-02-24",
            sample_size=None,
            response_rate=None,
            margin_of_error=None,
            sponsor=None,
            method=None,
            region_code="11-000",
            office_type="광역자치단체장",
            matchup_id="20260603|광역자치단체장|11-000",
            verified=False,
            source_grade="C",
            ingestion_run_id=None,
            evidence_text=article.raw_text[:200],
            source_url=article.url,
        )
        opt = PollOption(
            id=stable_id("opt", article.id),
            observation_id=obs.id,
            option_type="candidate",
            option_name="정원오",
            candidate_id="cand:jungwonoh",
            value_raw="44%",
            value_min=44.0,
            value_max=44.0,
            value_mid=44.0,
            is_missing=False,
            margin_of_error=None,
            evidence_text=article.raw_text,
        )
        return [obs], [opt], []


def test_live_news_pack_generates_ingest_payload_and_routes_low_completeness() -> None:
    out = build_collector_live_news_v1_pack(
        pipeline=FakePipeline(35),
        collector=FakeCollector(),
        threshold=0.8,
        target_count=40,
    )

    assert len(out["ingest_payload"]["records"]) == 35
    assert out["report"]["counts"]["threshold_miss_count"] == 35
    assert out["report"]["acceptance_checks"]["ingest_records_ge_30"] is True
    assert out["report"]["acceptance_checks"]["threshold_miss_review_queue_synced"] is True
    assert out["report"]["risk_signals"]["threshold_miss_present"] is True
    assert out["report"]["risk_signals"]["threshold_miss_count"] == 35

    issue_types = [x["issue_type"] for x in out["review_queue_candidates"]]
    assert "extract_error" in issue_types


def test_live_news_pack_raises_when_records_below_minimum() -> None:
    with pytest.raises(RuntimeError, match="insufficient live ingest records"):
        build_collector_live_news_v1_pack(
            pipeline=FakePipeline(10),
            collector=FakeCollector(),
            threshold=0.8,
            target_count=20,
        )

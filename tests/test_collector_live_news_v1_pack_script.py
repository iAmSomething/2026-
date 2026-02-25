from __future__ import annotations

import json
import pytest

from scripts.generate_collector_live_news_v1_pack import build_collector_live_news_v1_pack
from src.pipeline.contracts import Article, PollObservation, PollOption, stable_id
from src.pipeline.discovery_v11 import DiscoveryCandidateV11, DiscoveryResultV11


def _article(idx: int, *, host: str = "example.test", text: str | None = None) -> Article:
    body = text or f"서울시장 여론조사 정원오 4{idx%10}% vs 오세훈 3{idx%10}%"
    return Article(
        id=stable_id("art", str(idx)),
        url=f"https://{host}/{idx}",
        title=f"서울시장 조사 {idx}",
        publisher="테스트",
        published_at="2026-02-24T09:00:00+09:00",
        snippet=body[:120],
        collected_at="2026-02-24T00:00:00+00:00",
        raw_hash=stable_id("hash", body),
        raw_text=body,
    )


def _candidate(
    idx: int,
    *,
    host: str = "example.test",
    text: str | None = None,
    used_fallback: bool = False,
) -> DiscoveryCandidateV11:
    return DiscoveryCandidateV11(
        url=f"https://{host}/{idx}",
        title=f"서울시장 조사 {idx}",
        published_at_raw="Tue, 24 Feb 2026 09:00:00 +0900",
        query="지방선거 서울시장 여론조사",
        source_type="publisher_rss",
        article=_article(idx, host=host, text=text),
        used_fallback=used_fallback,
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


class RichTextCollector(FakeCollector):
    def extract(self, article: Article):
        article.raw_text = (
            article.raw_text
            + " 의뢰기관 서울신문, 표본수 1,001명, 응답률 12.3%, 오차범위 ±3.1%p."
        )
        return super().extract(article)


def test_live_news_pack_generates_ingest_payload_and_routes_low_completeness() -> None:
    out = build_collector_live_news_v1_pack(
        pipeline=FakePipeline(35),
        collector=FakeCollector(),
        threshold=0.8,
        target_count=40,
        nesdc_enrich_path=None,
        source_allowlist_domains=("example.test",),
    )

    assert len(out["ingest_payload"]["records"]) == 35
    assert out["report"]["counts"]["threshold_miss_count"] == 35
    assert out["report"]["acceptance_checks"]["ingest_records_ge_30"] is True
    assert out["report"]["acceptance_checks"]["threshold_miss_review_queue_synced"] is True
    assert out["report"]["risk_signals"]["threshold_miss_present"] is True
    assert out["report"]["risk_signals"]["threshold_miss_count"] == 35

    issue_types = [x["issue_type"] for x in out["review_queue_candidates"]]
    assert "extract_error" in issue_types
    threshold_items = [
        x for x in out["review_queue_candidates"] if x.get("error_code") == "LEGAL_COMPLETENESS_BELOW_THRESHOLD"
    ]
    assert threshold_items
    assert "missing_field_reasons" in (threshold_items[0].get("payload") or {})


def test_live_news_pack_raises_when_records_below_minimum() -> None:
    with pytest.raises(RuntimeError, match="insufficient live ingest records"):
        build_collector_live_news_v1_pack(
            pipeline=FakePipeline(10),
            collector=FakeCollector(),
            threshold=0.8,
            target_count=20,
            nesdc_enrich_path=None,
            source_allowlist_domains=("example.test",),
        )


def test_live_news_pack_article_rule_enrichment_improves_completeness() -> None:
    out = build_collector_live_news_v1_pack(
        pipeline=FakePipeline(35),
        collector=RichTextCollector(),
        threshold=0.8,
        target_count=40,
        nesdc_enrich_path=None,
        source_allowlist_domains=("example.test",),
    )

    assert out["report"]["counts"]["threshold_miss_count"] == 0
    assert out["report"]["legal_completeness"]["avg_score"] >= 0.8
    assert out["report"]["legal_enrichment"]["enriched_observation_count"] == 35
    assert out["report"]["legal_enrichment"]["enrichment_source_counts"]["article_pattern"] > 0


def test_live_news_pack_nesdc_enrichment_fills_numeric_fields(tmp_path) -> None:
    nesdc_rows = {
        "records": [
            {
                "pollster": "한국갤럽",
                "legal_meta": {
                    "survey_datetime": "2026-02-24",
                    "sample_size": 1000,
                    "response_rate": 10.2,
                    "margin_of_error": "95% 신뢰수준 ±3.1%P",
                },
            }
        ]
    }
    nesdc_path = tmp_path / "nesdc.json"
    nesdc_path.write_text(json.dumps(nesdc_rows, ensure_ascii=False), encoding="utf-8")

    out = build_collector_live_news_v1_pack(
        pipeline=FakePipeline(35),
        collector=FakeCollector(),
        threshold=0.8,
        target_count=40,
        nesdc_enrich_path=str(nesdc_path),
        source_allowlist_domains=("example.test",),
    )

    assert out["report"]["counts"]["threshold_miss_count"] == 0
    assert out["report"]["risk_signals"]["threshold_miss_rate"] == 0.0
    assert out["report"]["legal_enrichment"]["enrichment_source_counts"]["nesdc_meta"] > 0


def test_live_news_pack_source_quality_gate_blocks_low_quality_fallbacks() -> None:
    high_quality_text = (
        "서울시장 여론조사 지지율 가상대결 오차범위 응답률 표본 1000명 "
        "후보A 45.1% 후보B 38.9% "
        "여론조사 지지율 가상대결 오차범위 응답률 표본"
    )
    low_quality_text = "단신"

    class MixedPipeline:
        def run(self, *, target_count: int, per_query_limit: int, per_feed_limit: int) -> DiscoveryResultV11:  # noqa: ARG002
            result = DiscoveryResultV11()
            strong = [_candidate(i, text=high_quality_text, used_fallback=False) for i in range(30)]
            weak = [_candidate(100 + i, text=low_quality_text, used_fallback=True) for i in range(10)]
            all_candidates = strong + weak
            result.valid_candidates = list(all_candidates)
            result.fetched_candidates = list(all_candidates)
            result.deduped_candidates = list(all_candidates)
            result.raw_candidates = list(all_candidates)
            return result

    out = build_collector_live_news_v1_pack(
        pipeline=MixedPipeline(),
        collector=FakeCollector(),
        threshold=0.8,
        target_count=40,
        nesdc_enrich_path=None,
        source_allowlist_domains=(),
        source_quality_min_score=0.35,
        fallback_warn_threshold=0.2,
    )

    gate = out["report"]["source_quality_gate"]
    assert gate["candidate_in_count"] == 40
    assert gate["candidate_pass_count"] == 30
    assert gate["candidate_block_count"] == 10
    assert gate["fallback_ratio_pass"] < gate["fallback_ratio_in"]
    assert out["report"]["discovery_metrics"]["fallback_fetch_ratio_raw"] == 0.25
    assert out["report"]["discovery_metrics"]["fallback_fetch_ratio_post_gate"] == 0.0
    assert out["report"]["risk_signals"]["fallback_fetch_ratio_warn"] is True


def test_live_news_pack_auto_escalates_target_count_when_ingest_short() -> None:
    class AdaptivePipeline:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def run(self, *, target_count: int, per_query_limit: int, per_feed_limit: int) -> DiscoveryResultV11:  # noqa: ARG002
            self.calls.append(target_count)
            count = 25 if target_count < 160 else 35
            result = DiscoveryResultV11()
            result.valid_candidates = [_candidate(i, used_fallback=(i % 2 == 0)) for i in range(count)]
            result.fetched_candidates = list(result.valid_candidates)
            result.deduped_candidates = list(result.valid_candidates)
            result.raw_candidates = list(result.valid_candidates)
            return result

    pipeline = AdaptivePipeline()
    out = build_collector_live_news_v1_pack(
        pipeline=pipeline,
        collector=FakeCollector(),
        threshold=0.8,
        target_count=140,
        nesdc_enrich_path=None,
        source_allowlist_domains=("example.test",),
    )

    assert pipeline.calls == [140, 160]
    assert len(out["ingest_payload"]["records"]) == 35
    tuning = out["report"]["execution_tuning"]
    assert tuning["requested_target_count"] == 140
    assert tuning["effective_target_count"] == 160
    assert tuning["auto_escalation_applied"] is True
    assert len(tuning["attempts"]) == 2

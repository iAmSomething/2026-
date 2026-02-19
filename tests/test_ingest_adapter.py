from app.models.schemas import IngestPayload
from src.pipeline.collector import CollectorOutput, PollCollector
from src.pipeline.contracts import Article, stable_id
from src.pipeline.ingest_adapter import collector_output_to_ingest_payload


def test_collector_output_converts_to_ingest_payload():
    collector = PollCollector(election_id="20260603")
    output = CollectorOutput()

    text = "서울시장 여론조사 MBC 발표 정원오 44% vs 오세훈 31%"
    article = Article(
        id=stable_id("art", "1"),
        url="https://example.com/1",
        title="서울시장 조사",
        publisher="샘플",
        published_at="2026-02-18T00:00:00+09:00",
        snippet=text[:80],
        collected_at="2026-02-18T00:00:00+00:00",
        raw_hash=stable_id("hash", text),
        raw_text=text,
    )
    output.articles.append(article)
    obs, opts, errs = collector.extract(article)
    obs[0].audience_scope = "regional"
    obs[0].audience_region_code = "11-000"
    obs[0].sampling_population_text = "서울 성인"
    obs[0].legal_completeness_score = 0.71
    obs[0].legal_filled_count = 5
    obs[0].legal_required_count = 7
    obs[0].date_resolution = "exact"
    obs[0].date_inference_mode = "relative_published_at"
    obs[0].date_inference_confidence = 0.92
    obs[0].source_channel = "article"
    obs[0].source_channels = ["article"]
    output.poll_observations.extend(obs)
    output.poll_options.extend(opts)
    output.review_queue.extend(errs)

    payload = collector_output_to_ingest_payload(output)
    parsed = IngestPayload.model_validate(payload)
    assert len(parsed.records) == 1
    assert parsed.records[0].observation.office_type == "광역자치단체장"
    assert parsed.records[0].region is not None
    assert parsed.records[0].region.region_code == "11-000"
    assert parsed.records[0].observation.audience_scope == "regional"
    assert parsed.records[0].observation.legal_required_count == 7
    assert parsed.records[0].observation.source_channel == "article"
    assert parsed.records[0].observation.source_channels == ["article"]
    assert parsed.records[0].observation.date_inference_mode == "relative_published_at"

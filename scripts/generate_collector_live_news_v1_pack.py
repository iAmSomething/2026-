from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.pipeline.collector import CollectorOutput, PollCollector
from src.pipeline.contracts import Article, new_review_queue_item
from src.pipeline.discovery_v11 import DiscoveryPipelineV11, DiscoveryResultV11
from src.pipeline.ingest_adapter import collector_output_to_ingest_payload

OUT_CANDIDATES = "data/collector_live_news_v1_candidates.json"
OUT_OUTPUT = "data/collector_live_news_v1_output.json"
OUT_PAYLOAD = "data/collector_live_news_v1_payload.json"
OUT_REPORT = "data/collector_live_news_v1_report.json"
OUT_REVIEW_QUEUE = "data/collector_live_news_v1_review_queue_candidates.json"

REQUIRED_FIELDS: tuple[str, ...] = (
    "pollster",
    "sponsor",
    "survey_period",
    "sample_size",
    "response_rate",
    "margin_of_error",
)

DEFAULT_THRESHOLD = 0.8


@dataclass(frozen=True)
class CompletenessResult:
    score: float
    filled_count: int
    required_count: int
    missing_fields: list[str]


class _PipelineAdapter:
    def run(self, *, target_count: int, per_query_limit: int, per_feed_limit: int) -> DiscoveryResultV11:
        return DiscoveryPipelineV11().run(
            target_count=target_count,
            per_query_limit=per_query_limit,
            per_feed_limit=per_feed_limit,
        )


def _is_valid_numeric(name: str, value: Any) -> bool:
    if value is None:
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    if name == "sample_size":
        return numeric > 0 and float(numeric).is_integer()
    if name == "response_rate":
        return 0 < numeric <= 100
    if name == "margin_of_error":
        return 0 < numeric <= 100
    return False


def _compute_completeness(observation: dict[str, Any]) -> CompletenessResult:
    missing: list[str] = []

    pollster = str(observation.get("pollster") or "").strip()
    if not pollster:
        missing.append("pollster")

    sponsor = str(observation.get("sponsor") or "").strip()
    if not sponsor:
        missing.append("sponsor")

    if not (observation.get("survey_start_date") or observation.get("survey_end_date")):
        missing.append("survey_period")

    if not _is_valid_numeric("sample_size", observation.get("sample_size")):
        missing.append("sample_size")

    if not _is_valid_numeric("response_rate", observation.get("response_rate")):
        missing.append("response_rate")

    if not _is_valid_numeric("margin_of_error", observation.get("margin_of_error")):
        missing.append("margin_of_error")

    required_count = len(REQUIRED_FIELDS)
    filled_count = required_count - len(missing)
    score = round(filled_count / required_count, 4)
    return CompletenessResult(
        score=score,
        filled_count=filled_count,
        required_count=required_count,
        missing_fields=missing,
    )


def _article_to_dict(article: Article) -> dict[str, Any]:
    return {
        "id": article.id,
        "url": article.url,
        "title": article.title,
        "publisher": article.publisher,
        "published_at": article.published_at,
        "snippet": article.snippet,
        "collected_at": article.collected_at,
        "raw_hash": article.raw_hash,
        "raw_text": article.raw_text,
    }


def build_collector_live_news_v1_pack(
    *,
    target_count: int = 80,
    per_query_limit: int = 8,
    per_feed_limit: int = 30,
    threshold: float = DEFAULT_THRESHOLD,
    election_id: str = "20260603",
    pipeline: Any = None,
    collector: PollCollector | None = None,
) -> dict[str, Any]:
    pipeline_runner = pipeline or _PipelineAdapter()
    extractor = collector or PollCollector(election_id=election_id)

    discovery_result: DiscoveryResultV11 = pipeline_runner.run(
        target_count=target_count,
        per_query_limit=per_query_limit,
        per_feed_limit=per_feed_limit,
    )

    output = CollectorOutput()
    output.review_queue.extend(discovery_result.review_queue)

    seen_article_ids: set[str] = set()
    threshold_miss_count = 0
    threshold_routed_count = 0
    missing_counter: Counter[str] = Counter()

    for candidate in discovery_result.valid_candidates:
        article = candidate.article
        if article is None:
            continue
        if article.id not in seen_article_ids:
            output.articles.append(article)
            seen_article_ids.add(article.id)

        observations, options, extract_errors = extractor.extract(article)
        output.poll_observations.extend(observations)
        output.poll_options.extend(options)
        output.review_queue.extend(extract_errors)

        for obs in observations:
            obs_dict = obs.to_dict()
            completeness = _compute_completeness(obs_dict)
            obs.legal_completeness_score = completeness.score
            obs.legal_filled_count = completeness.filled_count
            obs.legal_required_count = completeness.required_count

            for field in completeness.missing_fields:
                missing_counter[field] += 1

            if completeness.score < threshold:
                threshold_miss_count += 1
                threshold_routed_count += 1
                output.review_queue.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=obs.id,
                        issue_type="extract_error",
                        stage="live_news_v1_legal",
                        error_code="LEGAL_COMPLETENESS_BELOW_THRESHOLD",
                        error_message="live news legal completeness below threshold",
                        source_url=obs.source_url,
                        payload={
                            "threshold": threshold,
                            "completeness_score": completeness.score,
                            "missing_fields": completeness.missing_fields,
                        },
                    )
                )

    ingest_payload = collector_output_to_ingest_payload(
        output,
        run_type="collector_live_news_v1",
        extractor_version="collector-live-news-v1",
    )

    if len(ingest_payload.get("records") or []) < 30:
        raise RuntimeError(
            f"insufficient live ingest records: got={len(ingest_payload.get('records') or [])}, required>=30"
        )

    candidate_preview = [c.classify_input() for c in discovery_result.valid_candidates[:100]]

    completeness_scores = [
        float(obs.legal_completeness_score or 0.0)
        for obs in output.poll_observations
    ]
    avg_score = round(sum(completeness_scores) / len(completeness_scores), 4) if completeness_scores else 0.0

    report = {
        "run_type": "collector_live_news_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovery_metrics": discovery_result.metrics(),
        "counts": {
            "article_count": len(output.articles),
            "observation_count": len(output.poll_observations),
            "option_count": len(output.poll_options),
            "review_queue_count": len(output.review_queue),
            "ingest_record_count": len(ingest_payload.get("records") or []),
            "threshold_miss_count": threshold_miss_count,
        },
        "legal_required_fields": list(REQUIRED_FIELDS),
        "legal_completeness": {
            "threshold": threshold,
            "avg_score": avg_score,
            "min_score": min(completeness_scores) if completeness_scores else 0.0,
            "max_score": max(completeness_scores) if completeness_scores else 0.0,
            "missing_field_counts": dict(missing_counter),
        },
        "acceptance_checks": {
            "live_news_candidates_present": len(candidate_preview) > 0,
            "ingest_records_ge_30": len(ingest_payload.get("records") or []) >= 30,
            "threshold_miss_review_queue_synced": threshold_routed_count == threshold_miss_count,
        },
        "risk_signals": {
            "threshold_miss_present": threshold_miss_count > 0,
            "threshold_miss_count": threshold_miss_count,
            "threshold_miss_rate": round(
                threshold_miss_count / max(1, len(output.poll_observations)),
                4,
            ),
        },
    }

    return {
        "candidate_preview": candidate_preview,
        "collector_output": output.to_dict(),
        "ingest_payload": ingest_payload,
        "report": report,
        "review_queue_candidates": [item.to_dict() for item in output.review_queue],
    }


def main() -> None:
    out = build_collector_live_news_v1_pack()

    Path(OUT_CANDIDATES).write_text(json.dumps(out["candidate_preview"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_OUTPUT).write_text(json.dumps(out["collector_output"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_PAYLOAD).write_text(json.dumps(out["ingest_payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_CANDIDATES)
    print("written:", OUT_OUTPUT)
    print("written:", OUT_PAYLOAD)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from src.pipeline.collector import CollectorOutput, PollCollector
from src.pipeline.contracts import Article, new_review_queue_item
from src.pipeline.discovery_v11 import DiscoveryCandidateV11, DiscoveryPipelineV11, DiscoveryResultV11
from src.pipeline.ingest_adapter import collector_output_to_ingest_payload

OUT_CANDIDATES = "data/collector_live_news_v1_candidates.json"
OUT_OUTPUT = "data/collector_live_news_v1_output.json"
OUT_PAYLOAD = "data/collector_live_news_v1_payload.json"
OUT_REPORT = "data/collector_live_news_v1_report.json"
OUT_REVIEW_QUEUE = "data/collector_live_news_v1_review_queue_candidates.json"
DEFAULT_NESDC_ENRICH_PATH = "data/collector_nesdc_safe_collect_v1.json"
SOURCE_ALLOWLIST_DOMAINS: tuple[str, ...] = (
    "yna.co.kr",
    "khan.co.kr",
    "chosun.com",
    "newsis.com",
    "hankyung.com",
    "mk.co.kr",
    "segye.com",
    "mbn.co.kr",
)
SOURCE_QUALITY_MIN_SCORE = 0.35
FALLBACK_FETCH_RATIO_WARN_THRESHOLD = 0.7

REQUIRED_FIELDS: tuple[str, ...] = (
    "pollster",
    "sponsor",
    "survey_period",
    "sample_size",
    "response_rate",
    "margin_of_error",
)

DEFAULT_THRESHOLD = 0.8
SPONSOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:의뢰(?:기관|처)?|의뢰자)\s*[:：]?\s*([A-Za-z0-9가-힣·\-\(\)\s]{2,40})"),
    re.compile(r"([A-Za-z0-9가-힣·\-\(\)\s]{2,40})\s*(?:의뢰로|의뢰를 받아)"),
)
SAMPLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:표본(?:수)?|조사(?:대상)?)[^\d]{0,12}([0-9][0-9,]{2,5})\s*명"),
    re.compile(r"\bN\s*=\s*([0-9][0-9,]{2,5})\b", flags=re.IGNORECASE),
)
RESPONSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"응답률[^\d]{0,10}([0-9]+(?:\.[0-9]+)?)\s*%"),
)
MARGIN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"오차범위[^\d]{0,14}(?:±|\+/-)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*[pP]?"),
    re.compile(r"(?:±|\+/-)\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*[pP]"),
)


@dataclass(frozen=True)
class CompletenessResult:
    score: float
    filled_count: int
    required_count: int
    missing_fields: list[str]
    missing_field_reasons: dict[str, str]


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


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if value <= 0:
            return None
        return int(value)
    text = str(value)
    m = re.search(r"([0-9][0-9,]*)", text)
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    try:
        parsed = int(digits)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if parsed > 0 else None
    text = str(value)
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not m:
        return None
    try:
        parsed = float(m.group(1))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _extract_first(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pat in patterns:
        m = pat.search(text)
        if not m:
            continue
        value = re.sub(r"\s+", " ", m.group(1)).strip(" ,.;:)]")
        if value:
            return value
    return None


def _extract_sample_size_from_text(text: str) -> int | None:
    for pat in SAMPLE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_int(m.group(1))
        if parsed is not None:
            return parsed
    return None


def _extract_response_rate_from_text(text: str) -> float | None:
    for pat in RESPONSE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_float(m.group(1))
        if parsed is not None and parsed <= 100:
            return parsed
    return None


def _extract_margin_of_error_from_text(text: str) -> float | None:
    for pat in MARGIN_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_float(m.group(1))
        if parsed is not None and parsed <= 100:
            return parsed
    return None


def _extract_survey_date_candidates(text: str) -> tuple[str | None, str | None]:
    dates = re.findall(r"(20[0-9]{2}-[0-9]{2}-[0-9]{2})", text)
    if not dates:
        return None, None
    ordered = sorted(set(dates))
    if len(ordered) == 1:
        return None, ordered[0]
    return ordered[0], ordered[-1]


def _normalize_pollster(value: str) -> str:
    text = value.lower().strip()
    text = text.replace("주식회사", "").replace("(주)", "").replace("㈜", "")
    text = re.sub(r"[^a-z0-9가-힣]", "", text)
    return text


def _load_nesdc_enrichment_index(path: str | None) -> dict[str, list[dict[str, Any]]]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    index: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("records") or []:
        pollster_raw = str(row.get("pollster") or "").strip()
        key = _normalize_pollster(pollster_raw)
        if not key:
            continue
        legal_meta = row.get("legal_meta") or {}
        start_date, end_date = _extract_survey_date_candidates(str(legal_meta.get("survey_datetime") or ""))
        item = {
            "pollster": pollster_raw,
            "sample_size": _parse_int(legal_meta.get("sample_size")),
            "response_rate": _parse_float(legal_meta.get("response_rate")),
            "margin_of_error": (
                _extract_margin_of_error_from_text(str(legal_meta.get("margin_of_error") or ""))
                or _parse_float(legal_meta.get("margin_of_error"))
            ),
            "survey_start_date": start_date,
            "survey_end_date": end_date,
        }
        index.setdefault(key, []).append(item)
    return index


def _pick_nesdc_enrichment(
    *,
    observation: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    obs_date = str(observation.get("survey_end_date") or observation.get("survey_start_date") or "")
    if not entries:
        return None
    if not obs_date:
        return entries[0]

    def score(entry: dict[str, Any]) -> tuple[int, int]:
        entry_date = str(entry.get("survey_end_date") or entry.get("survey_start_date") or "")
        exact = 0 if entry_date and entry_date == obs_date else 1
        completeness = 0
        if entry.get("sample_size") is not None:
            completeness += 1
        if entry.get("response_rate") is not None:
            completeness += 1
        if entry.get("margin_of_error") is not None:
            completeness += 1
        return (exact, -completeness)

    return sorted(entries, key=score)[0]


def _apply_observation_enrichment(
    *,
    observation: dict[str, Any],
    article_text: str,
    nesdc_index: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    applied: dict[str, str] = {}

    sponsor = str(observation.get("sponsor") or "").strip()
    if not sponsor:
        parsed_sponsor = _extract_first(article_text, SPONSOR_PATTERNS)
        if parsed_sponsor:
            observation["sponsor"] = parsed_sponsor
            applied["sponsor"] = "article_pattern"

    if not _is_valid_numeric("sample_size", observation.get("sample_size")):
        parsed_sample = _extract_sample_size_from_text(article_text)
        if parsed_sample is not None:
            observation["sample_size"] = parsed_sample
            applied["sample_size"] = "article_pattern"

    if not _is_valid_numeric("response_rate", observation.get("response_rate")):
        parsed_rate = _extract_response_rate_from_text(article_text)
        if parsed_rate is not None:
            observation["response_rate"] = parsed_rate
            applied["response_rate"] = "article_pattern"

    if not _is_valid_numeric("margin_of_error", observation.get("margin_of_error")):
        parsed_margin = _extract_margin_of_error_from_text(article_text)
        if parsed_margin is not None:
            observation["margin_of_error"] = parsed_margin
            applied["margin_of_error"] = "article_pattern"

    pollster_key = _normalize_pollster(str(observation.get("pollster") or ""))
    nesdc_entries = nesdc_index.get(pollster_key) or []
    best = _pick_nesdc_enrichment(observation=observation, entries=nesdc_entries)
    if not best:
        return applied

    if not _is_valid_numeric("sample_size", observation.get("sample_size")) and best.get("sample_size") is not None:
        observation["sample_size"] = best["sample_size"]
        applied["sample_size"] = "nesdc_meta"
    if not _is_valid_numeric("response_rate", observation.get("response_rate")) and best.get("response_rate") is not None:
        observation["response_rate"] = best["response_rate"]
        applied["response_rate"] = "nesdc_meta"
    if not _is_valid_numeric("margin_of_error", observation.get("margin_of_error")) and best.get("margin_of_error") is not None:
        observation["margin_of_error"] = best["margin_of_error"]
        applied["margin_of_error"] = "nesdc_meta"
    if not observation.get("survey_start_date") and best.get("survey_start_date"):
        observation["survey_start_date"] = best["survey_start_date"]
        applied["survey_period"] = "nesdc_meta"
    if not observation.get("survey_end_date") and best.get("survey_end_date"):
        observation["survey_end_date"] = best["survey_end_date"]
        applied["survey_period"] = "nesdc_meta"

    return applied


def _compute_completeness(observation: dict[str, Any]) -> CompletenessResult:
    missing: list[str] = []
    reasons: dict[str, str] = {}

    pollster = str(observation.get("pollster") or "").strip()
    if not pollster:
        missing.append("pollster")
        reasons["pollster"] = "empty_value"

    sponsor = str(observation.get("sponsor") or "").strip()
    if not sponsor:
        missing.append("sponsor")
        reasons["sponsor"] = "empty_value"

    if not (observation.get("survey_start_date") or observation.get("survey_end_date")):
        missing.append("survey_period")
        reasons["survey_period"] = "both_dates_missing"

    if not _is_valid_numeric("sample_size", observation.get("sample_size")):
        missing.append("sample_size")
        reasons["sample_size"] = "missing_or_invalid_numeric"

    if not _is_valid_numeric("response_rate", observation.get("response_rate")):
        missing.append("response_rate")
        reasons["response_rate"] = "missing_or_invalid_numeric"

    if not _is_valid_numeric("margin_of_error", observation.get("margin_of_error")):
        missing.append("margin_of_error")
        reasons["margin_of_error"] = "missing_or_invalid_numeric"

    required_count = len(REQUIRED_FIELDS)
    filled_count = required_count - len(missing)
    score = round(filled_count / required_count, 4)
    return CompletenessResult(
        score=score,
        filled_count=filled_count,
        required_count=required_count,
        missing_fields=missing,
        missing_field_reasons=reasons,
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


def _domain_from_url(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).netloc or "").lower()


def _is_allowlisted_domain(domain: str, allowlist: tuple[str, ...]) -> bool:
    normalized = domain.lower()
    for base in allowlist:
        if normalized == base or normalized.endswith("." + base):
            return True
    return False


def _body_quality_score(text: str) -> float:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return 0.0

    length_score = min(len(cleaned) / 1200.0, 1.0) * 0.45
    keyword_hits = sum(1 for k in ("여론조사", "지지율", "가상대결", "오차범위", "응답률", "표본") if k in cleaned)
    keyword_score = min(keyword_hits / 4.0, 1.0) * 0.35
    percent_score = 0.2 if re.search(r"\d{1,3}(?:\.\d+)?%", cleaned) else 0.0
    noise_penalty = 0.0
    if "기자 =" in cleaned or "무단전재" in cleaned:
        noise_penalty += 0.05
    score = max(0.0, min(1.0, length_score + keyword_score + percent_score - noise_penalty))
    return round(score, 4)


def _apply_source_quality_gate(
    *,
    candidates: list[DiscoveryCandidateV11],
    allowlist: tuple[str, ...],
    min_body_score: float,
) -> tuple[list[DiscoveryCandidateV11], dict[str, Any]]:
    passed: list[DiscoveryCandidateV11] = []
    blocked: list[dict[str, Any]] = []
    fallback_in = 0
    fallback_out = 0
    body_scores: list[float] = []

    for c in candidates:
        domain = _domain_from_url((c.article.url if c.article else None) or c.url)
        allowlisted = _is_allowlisted_domain(domain, allowlist)
        text = ""
        if c.article is not None:
            text = c.article.raw_text or c.article.snippet or ""
        if not text:
            text = " ".join(filter(None, [c.title, c.summary or "", c.query or ""]))
        body_score = _body_quality_score(text)
        body_scores.append(body_score)

        if c.used_fallback:
            fallback_in += 1

        passed_gate = allowlisted or body_score >= min_body_score
        if passed_gate:
            passed.append(c)
            if c.used_fallback:
                fallback_out += 1
            continue

        blocked.append(
            {
                "url": (c.article.url if c.article else None) or c.url,
                "source_type": c.source_type,
                "used_fallback": c.used_fallback,
                "domain": domain,
                "allowlisted": allowlisted,
                "body_quality_score": body_score,
            }
        )

    blocked_domain_count = sum(1 for x in blocked if not x.get("allowlisted"))
    blocked_quality_count = sum(1 for x in blocked if float(x.get("body_quality_score") or 0.0) < min_body_score)
    in_count = len(candidates)
    out_count = len(passed)
    metrics = {
        "allowlist_domain_count": len(allowlist),
        "min_body_quality_score": min_body_score,
        "candidate_in_count": in_count,
        "candidate_pass_count": out_count,
        "candidate_block_count": len(blocked),
        "blocked_by_domain_count": blocked_domain_count,
        "blocked_by_quality_count": blocked_quality_count,
        "fallback_in_count": fallback_in,
        "fallback_pass_count": fallback_out,
        "fallback_ratio_in": round(fallback_in / max(1, in_count), 4),
        "fallback_ratio_pass": round(fallback_out / max(1, out_count), 4) if out_count else 0.0,
        "avg_body_quality_score": round(sum(body_scores) / len(body_scores), 4) if body_scores else 0.0,
        "blocked_samples": blocked[:30],
    }
    return passed, metrics


def build_collector_live_news_v1_pack(
    *,
    target_count: int = 80,
    per_query_limit: int = 8,
    per_feed_limit: int = 30,
    threshold: float = DEFAULT_THRESHOLD,
    nesdc_enrich_path: str | None = DEFAULT_NESDC_ENRICH_PATH,
    source_allowlist_domains: tuple[str, ...] = SOURCE_ALLOWLIST_DOMAINS,
    source_quality_min_score: float = SOURCE_QUALITY_MIN_SCORE,
    fallback_warn_threshold: float = FALLBACK_FETCH_RATIO_WARN_THRESHOLD,
    election_id: str = "20260603",
    pipeline: Any = None,
    collector: PollCollector | None = None,
) -> dict[str, Any]:
    pipeline_runner = pipeline or _PipelineAdapter()
    extractor = collector or PollCollector(election_id=election_id)
    nesdc_index = _load_nesdc_enrichment_index(nesdc_enrich_path)

    discovery_result: DiscoveryResultV11 = pipeline_runner.run(
        target_count=target_count,
        per_query_limit=per_query_limit,
        per_feed_limit=per_feed_limit,
    )

    output = CollectorOutput()
    output.review_queue.extend(discovery_result.review_queue)
    discovery_metrics = discovery_result.metrics()
    gated_candidates, gate_metrics = _apply_source_quality_gate(
        candidates=list(discovery_result.valid_candidates),
        allowlist=source_allowlist_domains,
        min_body_score=source_quality_min_score,
    )

    seen_article_ids: set[str] = set()
    threshold_miss_count = 0
    threshold_routed_count = 0
    missing_counter: Counter[str] = Counter()
    enriched_field_counter: Counter[str] = Counter()
    enrichment_source_counter: Counter[str] = Counter()
    enriched_observation_count = 0

    for candidate in gated_candidates:
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
            applied_enrichment = _apply_observation_enrichment(
                observation=obs_dict,
                article_text=article.raw_text,
                nesdc_index=nesdc_index,
            )
            if applied_enrichment:
                enriched_observation_count += 1
                for field, source in applied_enrichment.items():
                    enriched_field_counter[field] += 1
                    enrichment_source_counter[source] += 1

            obs.sponsor = str(obs_dict.get("sponsor") or "").strip() or None
            obs.sample_size = _parse_int(obs_dict.get("sample_size"))
            obs.response_rate = _parse_float(obs_dict.get("response_rate"))
            obs.margin_of_error = _parse_float(obs_dict.get("margin_of_error"))
            obs.survey_start_date = str(obs_dict.get("survey_start_date") or "").strip() or None
            obs.survey_end_date = str(obs_dict.get("survey_end_date") or "").strip() or None

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
                            "missing_field_reasons": completeness.missing_field_reasons,
                            "enrichment_applied_fields": sorted(applied_enrichment.keys()),
                            "enrichment_sources": applied_enrichment,
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

    candidate_preview = [c.classify_input() for c in gated_candidates[:100]]

    completeness_scores = [
        float(obs.legal_completeness_score or 0.0)
        for obs in output.poll_observations
    ]
    avg_score = round(sum(completeness_scores) / len(completeness_scores), 4) if completeness_scores else 0.0
    fallback_fetch_ratio_raw = round(
        float(discovery_metrics.get("fallback_fetch_count") or 0) / max(1, int(discovery_metrics.get("fetched_count") or 0)),
        4,
    )
    fallback_ratio_post_gate = float(gate_metrics.get("fallback_ratio_pass") or 0.0)
    fallback_ratio_raw_over = fallback_fetch_ratio_raw > fallback_warn_threshold
    fallback_ratio_post_gate_over = fallback_ratio_post_gate > fallback_warn_threshold

    report = {
        "run_type": "collector_live_news_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovery_metrics": {
            **discovery_metrics,
            "fallback_fetch_ratio_raw": fallback_fetch_ratio_raw,
            "fallback_fetch_ratio_post_gate": fallback_ratio_post_gate,
        },
        "source_quality_gate": gate_metrics,
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
        "legal_enrichment": {
            "nesdc_enrich_path": nesdc_enrich_path,
            "nesdc_pollster_index_count": len(nesdc_index),
            "enriched_observation_count": enriched_observation_count,
            "enriched_field_counts": dict(enriched_field_counter),
            "enrichment_source_counts": dict(enrichment_source_counter),
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
            "fallback_fetch_ratio_raw": fallback_fetch_ratio_raw,
            "fallback_fetch_ratio_post_gate": fallback_ratio_post_gate,
            "fallback_fetch_ratio_threshold": fallback_warn_threshold,
            "fallback_fetch_ratio_raw_over_threshold": fallback_ratio_raw_over,
            "fallback_fetch_ratio_post_gate_over_threshold": fallback_ratio_post_gate_over,
            "fallback_fetch_ratio_warn": fallback_ratio_raw_over or fallback_ratio_post_gate_over,
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

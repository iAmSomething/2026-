from __future__ import annotations

from collections import defaultdict
from typing import Any

from .collector import CollectorOutput
from .standards import COMMON_CODE_REGIONS


def _option_type_for_ingest(option_type: str) -> str:
    if option_type == "candidate":
        return "candidate_matchup"
    return option_type


def collector_output_to_ingest_payload(
    output: CollectorOutput,
    *,
    run_type: str = "collector",
    extractor_version: str = "collector-v1",
    llm_model: str | None = None,
) -> dict[str, Any]:
    options_by_obs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for option in output.poll_options:
        options_by_obs[option.observation_id].append(option.to_dict())

    article_by_id = {article.id: article for article in output.articles}
    records: list[dict[str, Any]] = []
    for observation in output.poll_observations:
        article = article_by_id.get(observation.article_id)
        if article is None:
            continue

        region_meta = COMMON_CODE_REGIONS.get(observation.region_code)
        if region_meta is None:
            continue

        row_options = options_by_obs.get(observation.id, [])
        candidates: list[dict[str, Any]] = []
        seen_candidate: set[str] = set()
        for option in row_options:
            if option["option_type"] != "candidate":
                continue
            candidate_id = option["candidate_id"]
            if candidate_id in seen_candidate:
                continue
            seen_candidate.add(candidate_id)
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "name_ko": option["option_name"],
                    "party_name": None,
                    "gender": None,
                    "birth_date": None,
                    "job": None,
                    "career_summary": None,
                    "election_history": None,
                }
            )

        records.append(
            {
                "article": {
                    "url": article.url,
                    "title": article.title,
                    "publisher": article.publisher,
                    "published_at": article.published_at,
                    "raw_text": article.raw_text,
                    "raw_hash": article.raw_hash,
                },
                "region": {
                    "region_code": region_meta.region_code,
                    "sido_name": region_meta.sido_name,
                    "sigungu_name": region_meta.sigungu_name,
                    "admin_level": region_meta.admin_level,
                    "parent_region_code": region_meta.parent_region_code,
                },
                "candidates": candidates,
                "observation": {
                    "observation_key": observation.id,
                    "survey_name": observation.survey_name or article.title,
                    "pollster": observation.pollster or "미상조사기관",
                    "survey_start_date": observation.survey_start_date,
                    "survey_end_date": observation.survey_end_date,
                    "sample_size": observation.sample_size,
                    "response_rate": observation.response_rate,
                    "margin_of_error": observation.margin_of_error,
                    "sponsor": getattr(observation, "sponsor", None),
                    "method": getattr(observation, "method", None),
                    "region_code": observation.region_code,
                    "office_type": observation.office_type,
                    "matchup_id": observation.matchup_id,
                    "audience_scope": getattr(observation, "audience_scope", None),
                    "audience_region_code": getattr(observation, "audience_region_code", None),
                    "sampling_population_text": getattr(observation, "sampling_population_text", None),
                    "legal_completeness_score": getattr(observation, "legal_completeness_score", None),
                    "legal_filled_count": getattr(observation, "legal_filled_count", None),
                    "legal_required_count": getattr(observation, "legal_required_count", None),
                    "date_resolution": getattr(observation, "date_resolution", None),
                    "poll_fingerprint": getattr(observation, "poll_fingerprint", None),
                    "source_channel": getattr(observation, "source_channel", "article"),
                    "source_channels": getattr(observation, "source_channels", None),
                    "verified": observation.verified,
                    "source_grade": observation.source_grade or "C",
                },
                "options": [
                    {
                        "option_type": _option_type_for_ingest(option["option_type"]),
                        "option_name": option["option_name"],
                        "value_raw": option["value_raw"],
                        "value_min": option["value_min"],
                        "value_max": option["value_max"],
                        "value_mid": option["value_mid"],
                        "is_missing": option["is_missing"],
                    }
                    for option in row_options
                ],
            }
        )

    return {
        "run_type": run_type,
        "extractor_version": extractor_version,
        "llm_model": llm_model,
        "records": records,
    }

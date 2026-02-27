#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from app.models.schemas import IngestPayload
from app.services.cutoff_policy import ARTICLE_PUBLISHED_AT_CUTOFF_KST, has_article_source, parse_datetime_like
from app.services.ingest_input_normalization import normalize_ingest_payload
from app.services.ingest_service import ingest_payload

INPUT_PAYLOAD = Path("data/collector_live_coverage_v2_payload.json")
OUT_EVAL = Path("data/issue465_scope_hardguard_cutoff_eval.json")
OUT_SAMPLES = Path("data/issue465_scope_hardguard_cutoff_eval_samples.json")
FORCED_CUTOFF_PUBLISHED_AT = "2025-11-30T23:59:59+09:00"
HARDGUARD_KEYWORDS = (
    "서울시장",
    "부산시장",
    "대구시장",
    "인천시장",
    "광주시장",
    "대전시장",
    "울산시장",
    "세종시장",
    "경기도지사",
    "경기지사",
    "강원특별자치도지사",
    "강원도지사",
    "강원지사",
    "충청북도지사",
    "충북지사",
    "충청남도지사",
    "충남지사",
    "전북특별자치도지사",
    "전라북도지사",
    "전북지사",
    "전라남도지사",
    "전남지사",
    "경상북도지사",
    "경북지사",
    "경상남도지사",
    "경남지사",
    "제주특별자치도지사",
    "제주도지사",
    "제주지사",
)


class EvalRepo:
    def __init__(self) -> None:
        self._run_id = 0
        self.review: list[tuple[str, str, str, str]] = []
        self.observations: dict[str, dict[str, Any]] = {}
        self.option_rows: list[tuple[int, dict[str, Any]]] = []
        self.articles: dict[str, dict[str, Any]] = {}

    def create_ingestion_run(self, run_type, extractor_version, llm_model):  # noqa: ANN001, ARG002
        self._run_id += 1
        return self._run_id

    def finish_ingestion_run(self, run_id, status, processed_count, error_count):  # noqa: ANN001, ARG002
        return None

    def upsert_region(self, region):  # noqa: ANN001, ARG002
        return None

    def upsert_matchup(self, matchup):  # noqa: ANN001, ARG002
        return None

    def upsert_candidate(self, candidate):  # noqa: ANN001, ARG002
        return None

    def upsert_article(self, article):  # noqa: ANN001
        self.articles[article["url"]] = article
        return len(self.articles)

    def upsert_poll_observation(self, observation, article_id, ingestion_run_id):  # noqa: ANN001, ARG002
        self.observations[observation["observation_key"]] = observation
        return len(self.observations)

    def upsert_poll_option(self, observation_id, option):  # noqa: ANN001
        self.option_rows.append((observation_id, option))
        return None

    def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):  # noqa: ANN001
        self.review.append((entity_type, entity_id, issue_type, review_note))
        return None


def _compact(value: Any) -> str:
    return str(value or "").replace(" ", "")


def _find_hardguard_keyword(record: dict[str, Any]) -> str | None:
    text = "".join(
        (
            _compact(record.get("article", {}).get("title")),
            _compact(record.get("article", {}).get("raw_text")),
            _compact(record.get("observation", {}).get("survey_name")),
        )
    )
    for keyword in HARDGUARD_KEYWORDS:
        if keyword in text:
            return keyword
    return None


def _is_old_article(record: dict[str, Any]) -> bool:
    observation = record.get("observation", {})
    article = record.get("article", {})
    if not has_article_source(observation.get("source_channel"), observation.get("source_channels")):
        return False
    parsed = parse_datetime_like(article.get("published_at"))
    return parsed is not None and parsed < ARTICLE_PUBLISHED_AT_CUTOFF_KST


def _build_eval_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    records = payload.get("records") or []
    if len(records) < 30:
        raise RuntimeError(f"expected at least 30 records, got {len(records)}")

    # Force one old-article cutoff case.
    records[0]["article"]["published_at"] = FORCED_CUTOFF_PUBLISHED_AT

    # Force one scenario_parse_incomplete case.
    records[1]["article"]["title"] = "부산시장 다자대결"
    records[1]["article"]["raw_text"] = "부산시장 다자대결"
    records[1]["observation"]["survey_name"] = "부산시장 다자대결"
    records[1]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "40%"},
        {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "31%"},
    ]

    return normalize_ingest_payload(payload)


def main() -> int:
    raw_payload = json.loads(INPUT_PAYLOAD.read_text(encoding="utf-8"))
    normalized_payload = _build_eval_payload(raw_payload)
    records = normalized_payload.get("records") or []

    contains_reference_719065 = any("719065" in str((row.get("article") or {}).get("url") or "") for row in records)
    keyword_records = []
    old_article_keys = []
    pre_by_key: dict[str, dict[str, Any]] = {}
    for row in records:
        observation = row.get("observation") or {}
        observation_key = str(observation.get("observation_key") or "")
        if not observation_key:
            continue
        pre_by_key[observation_key] = {
            "office_type": observation.get("office_type"),
            "region_code": observation.get("region_code"),
            "matchup_id": observation.get("matchup_id"),
            "keyword": _find_hardguard_keyword(row),
            "survey_name": observation.get("survey_name"),
        }
        if pre_by_key[observation_key]["keyword"]:
            keyword_records.append(observation_key)
        if _is_old_article(row):
            old_article_keys.append(observation_key)

    payload = IngestPayload.model_validate(normalized_payload)
    repo = EvalRepo()
    result = ingest_payload(payload, repo)

    keyword_violations: list[dict[str, Any]] = []
    keyword_samples: list[dict[str, Any]] = []
    for key in keyword_records:
        post = repo.observations.get(key)
        if post is None:
            continue
        pre = pre_by_key.get(key, {})
        sample = {
            "observation_key": key,
            "keyword": pre.get("keyword"),
            "before": {
                "office_type": pre.get("office_type"),
                "region_code": pre.get("region_code"),
                "matchup_id": pre.get("matchup_id"),
            },
            "after": {
                "office_type": post.get("office_type"),
                "region_code": post.get("region_code"),
                "matchup_id": post.get("matchup_id"),
            },
        }
        keyword_samples.append(sample)
        if post.get("office_type") != "광역자치단체장" or not str(post.get("region_code") or "").endswith("-000"):
            keyword_violations.append(sample)

    scenario_reviews = [row for row in repo.review if row[2] == "scenario_parse_incomplete"]
    cutoff_reviews = [row for row in repo.review if "reason=old_article_cutoff" in row[3]]
    old_article_ingested = [key for key in old_article_keys if key in repo.observations]

    report = {
        "issue": 465,
        "algorithm_version": "scope_hardguard_cutoff_v1",
        "sample_count": len(records),
        "processed_count": result.processed_count,
        "error_count": result.error_count,
        "contains_reference_719065": contains_reference_719065,
        "keyword_record_count": len(keyword_records),
        "keyword_ingested_count": len(keyword_samples),
        "keyword_violation_count": len(keyword_violations),
        "old_article_record_count": len(old_article_keys),
        "old_article_ingested_count": len(old_article_ingested),
        "old_article_cutoff_review_count": len(cutoff_reviews),
        "scenario_parse_incomplete_review_count": len(scenario_reviews),
        "acceptance_checks": {
            "sample_count_ge_30": len(records) >= 30,
            "hardguard_basic_scope_violation_zero": len(keyword_violations) == 0,
            "old_article_ingest_zero": len(old_article_ingested) == 0,
            "old_article_cutoff_review_logged": len(cutoff_reviews) >= 1,
            "scenario_parse_incomplete_review_logged": len(scenario_reviews) >= 1,
        },
    }

    samples = {
        "mutations": {
            "forced_cutoff_observation_key": old_article_keys[0] if old_article_keys else None,
            "forced_cutoff_published_at": FORCED_CUTOFF_PUBLISHED_AT,
            "forced_scenario_observation_key": records[1].get("observation", {}).get("observation_key"),
        },
        "keyword_samples": keyword_samples[:20],
        "keyword_violations": keyword_violations,
        "old_article_cutoff_reviews": [
            {"entity_id": row[1], "issue_type": row[2], "review_note": row[3]}
            for row in cutoff_reviews[:10]
        ],
        "scenario_parse_incomplete_reviews": [
            {"entity_id": row[1], "issue_type": row[2], "review_note": row[3]}
            for row in scenario_reviews[:10]
        ],
    }

    OUT_EVAL.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SAMPLES.write_text(json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {OUT_EVAL}")
    print(f"written: {OUT_SAMPLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

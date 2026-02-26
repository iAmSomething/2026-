from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from typing import Any

from src.pipeline.contracts import new_review_queue_item

OUT_PAYLOAD = "data/collector_summary_nonempty_prod_payload.json"
OUT_REPORT = "data/collector_summary_nonempty_prod_report.json"
OUT_REVIEW_QUEUE = "data/collector_summary_nonempty_prod_review_queue_candidates.json"
OUT_SUMMARY_EXPECTED = "data/collector_summary_nonempty_prod_summary_expected.json"

SUMMARY_DATE_CUTOFF = date(2025, 12, 1)
LEGAL_COMPLETENESS_THRESHOLD = 0.8


def _source_priority(observation: dict[str, Any]) -> str:
    channels = {str(x).strip().lower() for x in (observation.get("source_channels") or []) if x}
    source_channel = str(observation.get("source_channel") or "").strip().lower()
    if source_channel:
        channels.add(source_channel)
    has_article = "article" in channels
    has_nesdc = "nesdc" in channels
    if has_article and has_nesdc:
        return "mixed"
    if has_nesdc:
        return "official"
    return "article"


def _build_record(*, legal_completeness_score: float) -> dict[str, Any]:
    return {
        "article": {
            "url": "https://www.nesdc.go.kr/portal/main.do",
            "title": "전국지표조사(NBS) 2026년 2월 4주 결과",
            "publisher": "NBS",
            "published_at": "2026-02-26T09:00:00+09:00",
            "raw_text": (
                "보조출처: https://www.mk.co.kr/news/politics/11972663 "
                "https://news.nate.com/view/20260226n15513 "
                "https://www.donga.com/news/Politics/article/all/20260226/133427602/2"
            ),
            "raw_hash": "summary-nonempty-prod-v1",
        },
        "region": {
            "region_code": "11-000",
            "sido_name": "서울특별시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
        "candidates": [],
        "observation": {
            "observation_key": "obs-summary-nonempty-20260225-nbs",
            "survey_name": "전국지표조사(NBS) 2월 4주",
            "pollster": "NBS",
            "survey_start_date": "2026-02-23",
            "survey_end_date": "2026-02-25",
            "sample_size": 1002,
            "response_rate": 14.9,
            "margin_of_error": 3.1,
            "sponsor": "NBS",
            "method": "휴대전화 가상번호 100% 전화면접",
            "region_code": "11-000",
            "office_type": "광역자치단체장",
            "matchup_id": "20260603|광역자치단체장|11-000",
            "audience_scope": "national",
            "audience_region_code": None,
            "sampling_population_text": "전국 만 18세 이상 남녀",
            "legal_completeness_score": legal_completeness_score,
            "legal_filled_count": 7,
            "legal_required_count": 7,
            "date_resolution": "exact",
            "date_inference_mode": None,
            "date_inference_confidence": None,
            "source_channel": "nesdc",
            "source_channels": ["nesdc", "article"],
            "official_release_at": "2026-02-26T09:00:00+09:00",
            "verified": True,
            "source_grade": "A",
        },
        "options": [
            {"option_type": "party_support", "option_name": "더불어민주당", "value_raw": "45%"},
            {"option_type": "party_support", "option_name": "국민의힘", "value_raw": "17%"},
            {"option_type": "party_support", "option_name": "조국혁신당", "value_raw": "4%"},
            {"option_type": "party_support", "option_name": "개혁신당", "value_raw": "3%"},
            {"option_type": "party_support", "option_name": "진보당", "value_raw": "1%"},
            {"option_type": "party_support", "option_name": "태도유보", "value_raw": "27%"},
            {"option_type": "president_job_approval", "option_name": "대통령 직무 긍정평가", "value_raw": "67%"},
            {"option_type": "president_job_approval", "option_name": "대통령 직무 부정평가", "value_raw": "25%"},
            {"option_type": "election_frame", "option_name": "국정안정론", "value_raw": "53%"},
            {"option_type": "election_frame", "option_name": "국정견제론", "value_raw": "34%"},
        ],
    }


def _build_summary_expected(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    observation = record["observation"]
    source_priority = _source_priority(observation)
    grouped: dict[str, list[dict[str, Any]]] = {
        "party_support": [],
        "president_job_approval": [],
        "election_frame": [],
    }
    for option in record["options"]:
        option_type = option["option_type"]
        if option_type not in grouped:
            continue
        grouped[option_type].append(
            {
                "option_name": option["option_name"],
                "value_raw": option["value_raw"],
                "survey_end_date": observation["survey_end_date"],
                "audience_scope": observation["audience_scope"],
                "source_priority": source_priority,
            }
        )
    return grouped


def build_summary_nonempty_prod_pack(*, legal_completeness_score: float = 0.86) -> dict[str, Any]:
    record = _build_record(legal_completeness_score=legal_completeness_score)
    payload = {
        "run_type": "collector_summary_nonempty_prod",
        "extractor_version": "collector-summary-nonempty-prod-v1",
        "llm_model": None,
        "records": [deepcopy(record)],
    }

    observation = record["observation"]
    summary_expected = _build_summary_expected(record)

    option_type_counts: dict[str, int] = {}
    for option in record["options"]:
        key = option["option_type"]
        option_type_counts[key] = option_type_counts.get(key, 0) + 1

    review_queue_candidates: list[dict[str, Any]] = []
    if float(observation["legal_completeness_score"]) < LEGAL_COMPLETENESS_THRESHOLD:
        review_queue_candidates.append(
            new_review_queue_item(
                entity_type="poll_observation",
                entity_id=observation["observation_key"],
                issue_type="extract_error",
                stage="summary_nonempty_prod",
                error_code="LEGAL_COMPLETENESS_BELOW_THRESHOLD",
                error_message="legal completeness score below threshold",
                source_url=record["article"]["url"],
                payload={
                    "score": observation["legal_completeness_score"],
                    "threshold": LEGAL_COMPLETENESS_THRESHOLD,
                },
            ).to_dict()
        )

    survey_end_date = date.fromisoformat(observation["survey_end_date"])
    source_priority = _source_priority(observation)
    acceptance_checks = {
        "summary_three_option_types_nonempty": all(
            len(summary_expected[key]) >= 1 for key in ("party_support", "president_job_approval", "election_frame")
        ),
        "national_scope_only": all(
            row.get("audience_scope") == "national"
            for key in ("party_support", "president_job_approval", "election_frame")
            for row in summary_expected[key]
        ),
        "latest_not_before_2025_12_01": survey_end_date >= SUMMARY_DATE_CUTOFF,
        "source_priority_allowed": source_priority in {"official", "mixed", "article"},
    }

    report = {
        "run_type": payload["run_type"],
        "summary_date_cutoff": SUMMARY_DATE_CUTOFF.isoformat(),
        "observation_key": observation["observation_key"],
        "option_type_counts": option_type_counts,
        "source_priority": source_priority,
        "review_queue_candidate_count": len(review_queue_candidates),
        "acceptance_checks": acceptance_checks,
    }

    return {
        "payload": payload,
        "report": report,
        "review_queue_candidates": review_queue_candidates,
        "summary_expected": summary_expected,
    }


def main() -> None:
    out = build_summary_nonempty_prod_pack()
    Path(OUT_PAYLOAD).write_text(json.dumps(out["payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(OUT_SUMMARY_EXPECTED).write_text(
        json.dumps(out["summary_expected"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_PAYLOAD)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)
    print("written:", OUT_SUMMARY_EXPECTED)


if __name__ == "__main__":
    main()

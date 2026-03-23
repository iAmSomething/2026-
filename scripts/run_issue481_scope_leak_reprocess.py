#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.models.schemas import IngestPayload
from app.services.ingest_input_normalization import normalize_ingest_payload
from app.services.ingest_service import ingest_payload
from src.pipeline.standards import COMMON_CODE_REGIONS

INPUT_PAYLOAD = Path("data/collector_live_coverage_v2_payload.json")
OUT_KEYSET = Path("data/issue481_scope_leak_keys.json")
OUT_REPROCESS_PAYLOAD = Path("data/issue481_scope_leak_reprocess_payload.json")
OUT_REPROCESS_REPORT = Path("data/issue481_scope_leak_reprocess_report.json")
OUT_QA_PROBE = Path("data/issue481_scope_leak_qa_probe.json")

TARGET_REGION_CODES = {"26-710", "28-450"}
LEAK_KEYWORDS = ("부산시장", "인천시장")


class EvalRepo:
    def __init__(self) -> None:
        self._run_id = 0
        self.observations: dict[str, dict[str, Any]] = {}
        self.review: list[tuple[str, str, str, str]] = []

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

    def upsert_article(self, article):  # noqa: ANN001, ARG002
        return 1

    def upsert_poll_observation(self, observation, article_id, ingestion_run_id):  # noqa: ANN001, ARG002
        self.observations[observation["observation_key"]] = observation
        return len(self.observations)

    def upsert_poll_option(self, observation_id, option):  # noqa: ANN001, ARG002
        return None

    def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):  # noqa: ANN001
        self.review.append((entity_type, entity_id, issue_type, review_note))
        return None


def _record_observation(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("observation") or {}


def _record_region(record: dict[str, Any]) -> dict[str, Any] | None:
    region = record.get("region")
    return region if isinstance(region, dict) else None


def _observation_key(record: dict[str, Any]) -> str:
    return str(_record_observation(record).get("observation_key") or "").strip()


def _is_target_record(record: dict[str, Any]) -> bool:
    observation = _record_observation(record)
    if str(observation.get("region_code") or "").strip() not in TARGET_REGION_CODES:
        return False
    return _contains_leak_keyword(
        (record.get("article") or {}).get("title"),
        (record.get("article") or {}).get("raw_text"),
        observation.get("survey_name"),
    )


def _contains_leak_keyword(*values: Any) -> bool:
    text = " ".join(str(v or "") for v in values)
    return any(keyword in text for keyword in LEAK_KEYWORDS)


def _canonical_title(region_code: str | None, office_type: str | None, fallback: str) -> str:
    meta = COMMON_CODE_REGIONS.get(str(region_code or "").strip())
    if meta is None:
        return fallback

    sido_name = str(meta.sido_name or "").strip()
    sigungu_name = str(meta.sigungu_name or "").strip()
    office = str(office_type or "").strip()

    if office == "광역자치단체장":
        if sido_name.endswith(("특별시", "광역시", "특별자치시", "자치시")):
            base = sido_name
            for suffix in ("특별자치시", "특별시", "광역시", "자치시"):
                base = base.removesuffix(suffix)
            return f"{base}시장"
        if sido_name.endswith(("도", "특별자치도")):
            base = sido_name.removesuffix("특별자치도").removesuffix("도")
            return f"{base}도지사"
    if office == "기초자치단체장":
        target = sigungu_name if sigungu_name and sigungu_name != "전체" else sido_name
        if target.endswith("구"):
            return f"{target}청장"
        if target.endswith("군"):
            return f"{target}수"
        if target.endswith("시"):
            return f"{target}장"
    return fallback


def _default_region_payload(region_code: str) -> dict[str, Any]:
    meta = COMMON_CODE_REGIONS.get(region_code)
    if meta is None:
        return {
            "region_code": region_code,
            "sido_name": "",
            "sigungu_name": "전체" if region_code.endswith("-000") else "",
            "admin_level": "sido" if region_code.endswith("-000") else "sigungu",
            "parent_region_code": None if region_code.endswith("-000") else f"{region_code[:2]}-000",
        }
    return {
        "region_code": meta.region_code,
        "sido_name": meta.sido_name,
        "sigungu_name": meta.sigungu_name,
        "admin_level": meta.admin_level,
        "parent_region_code": meta.parent_region_code,
    }


def run_reprocess(
    *,
    input_payload_path: Path = INPUT_PAYLOAD,
    out_keyset_path: Path = OUT_KEYSET,
    out_reprocess_payload_path: Path = OUT_REPROCESS_PAYLOAD,
    out_reprocess_report_path: Path = OUT_REPROCESS_REPORT,
    out_qa_probe_path: Path = OUT_QA_PROBE,
) -> dict[str, Any]:
    raw_payload = json.loads(input_payload_path.read_text(encoding="utf-8"))
    normalized_payload = normalize_ingest_payload(raw_payload)
    records = normalized_payload.get("records") or []
    contains_reference_719065 = any("719065" in str((row.get("article") or {}).get("url") or "") for row in records)

    target_records = [row for row in records if _is_target_record(row)]
    target_keys = [_observation_key(row) for row in target_records if _observation_key(row)]
    pre_by_key = {
        _observation_key(row): {
            "observation_key": _observation_key(row),
            "region_code": _record_observation(row).get("region_code"),
            "office_type": _record_observation(row).get("office_type"),
            "matchup_id": _record_observation(row).get("matchup_id"),
            "article_title": (row.get("article") or {}).get("title"),
            "canonical_title": _canonical_title(
                _record_observation(row).get("region_code"),
                _record_observation(row).get("office_type"),
                str(_record_observation(row).get("survey_name") or ""),
            ),
            "leak_keyword_detected": _contains_leak_keyword(
                (row.get("article") or {}).get("title"),
                (row.get("article") or {}).get("raw_text"),
                _record_observation(row).get("survey_name"),
            ),
        }
        for row in target_records
    }

    payload = IngestPayload.model_validate(normalized_payload)
    repo = EvalRepo()
    ingest_result = ingest_payload(payload, repo)

    before_after_items: list[dict[str, Any]] = []
    corrected_records: list[dict[str, Any]] = []
    for row in target_records:
        key = _observation_key(row)
        if not key:
            continue
        post = repo.observations.get(key)
        if not post:
            continue
        pre = pre_by_key.get(key, {})

        before_after_items.append(
            {
                "observation_key": key,
                "before": {
                    "region_code": pre.get("region_code"),
                    "office_type": pre.get("office_type"),
                    "matchup_id": pre.get("matchup_id"),
                    "article_title": pre.get("article_title"),
                    "canonical_title": pre.get("canonical_title"),
                },
                "after": {
                    "region_code": post.get("region_code"),
                    "office_type": post.get("office_type"),
                    "matchup_id": post.get("matchup_id"),
                    "article_title": pre.get("article_title"),
                    "canonical_title": _canonical_title(
                        post.get("region_code"),
                        post.get("office_type"),
                        str(post.get("survey_name") or ""),
                    ),
                },
                "leak_keyword_detected_before": bool(pre.get("leak_keyword_detected")),
            }
        )

        corrected = deepcopy(row)
        corrected_observation = corrected.get("observation") or {}
        corrected_observation["region_code"] = post.get("region_code")
        corrected_observation["office_type"] = post.get("office_type")
        corrected_observation["matchup_id"] = post.get("matchup_id")
        corrected_observation["audience_scope"] = post.get("audience_scope")
        corrected_observation["audience_region_code"] = post.get("audience_region_code")
        corrected["observation"] = corrected_observation
        corrected["region"] = _default_region_payload(str(post.get("region_code") or ""))
        corrected_records.append(corrected)

    qa_failures = [
        item
        for item in before_after_items
        if item["after"]["office_type"] != "광역자치단체장"
        or not str(item["after"]["region_code"] or "").endswith("-000")
        or str(item["after"]["region_code"] or "") in TARGET_REGION_CODES
    ]
    leak_keyword_still_local = [
        item
        for item in before_after_items
        if item["leak_keyword_detected_before"] and str(item["after"]["region_code"] or "") in TARGET_REGION_CODES
    ]

    out_keyset_path.write_text(json.dumps(target_keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_reprocess_payload_path.write_text(
        json.dumps(
            {
                "run_type": "collector_issue481_scope_leak_reprocess_v1",
                "extractor_version": "collector-issue481-scope-leak-reprocess-v1",
                "llm_model": normalized_payload.get("llm_model"),
                "records": corrected_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = {
        "issue": 481,
        "input_payload_path": str(input_payload_path),
        "target_region_codes": sorted(TARGET_REGION_CODES),
        "contains_reference_719065": contains_reference_719065,
        "ingest_processed_count": ingest_result.processed_count,
        "ingest_error_count": ingest_result.error_count,
        "target_record_count": len(target_records),
        "corrected_record_count": len(corrected_records),
        "qa_failure_count": len(qa_failures),
        "leak_keyword_still_local_count": len(leak_keyword_still_local),
        "acceptance_checks": {
            "target_keyset_reprocess_ready": len(target_keys) > 0 and len(corrected_records) == len(target_records),
            "scope_leak_keywords_removed_for_target_locals": len(leak_keyword_still_local) == 0,
            "scope_related_fail_zero_for_targets": len(qa_failures) == 0,
        },
        "items": before_after_items,
    }
    out_reprocess_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    qa_probe = {
        "issue": 481,
        "probe_name": "scope_scenario_regression_gate_target_probe_v1",
        "target_keys": target_keys,
        "scope_fail_count": len(qa_failures),
        "scope_failures": qa_failures,
        "pass": len(qa_failures) == 0,
    }
    out_qa_probe_path.write_text(json.dumps(qa_probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_reprocess()
    print(f"written: {OUT_KEYSET}")
    print(f"written: {OUT_REPROCESS_PAYLOAD}")
    print(f"written: {OUT_REPROCESS_REPORT}")
    print(f"written: {OUT_QA_PROBE}")
    print(f"target_record_count={report['target_record_count']}")
    print(f"qa_failure_count={report['qa_failure_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

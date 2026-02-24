from __future__ import annotations

from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from scripts.generate_nesdc_safe_collect_v1 import generate_nesdc_safe_collect_v1
from src.pipeline.contracts import new_review_queue_item

INPUT_ARTICLE_PAYLOAD = "data/collector_live_news_v1_payload.json"

OUT_DATA = "data/nesdc_live_v1.json"
OUT_REPORT = "data/nesdc_live_v1_report.json"
OUT_REVIEW_QUEUE = "data/nesdc_live_v1_review_queue_candidates.json"
OUT_MERGE_EVIDENCE = "data/nesdc_live_v1_merge_policy_evidence.json"


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_optional_article_payload(path: str) -> tuple[dict[str, Any], bool]:
    file_path = Path(path)
    if not file_path.exists():
        return {"records": []}, False
    return _parse_json(path), True


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _parse_margin_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)

    # Prefer explicit margin markers (e.g., "±3.1%p", "+/-3.1%p").
    m = re.search(r"±\s*([0-9]+(?:\.[0-9]+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    m = re.search(r"\+/-\s*([0-9]+(?:\.[0-9]+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    numbers = re.findall(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not numbers:
        return None

    # For strings like "95% 신뢰수준 ±3.1%p", keep the last number as margin.
    if len(numbers) >= 2 and ("신뢰수준" in text or "confidence" in text.lower()):
        target = numbers[-1]
    else:
        target = numbers[0]

    try:
        return float(target)
    except ValueError:
        return None


def _parse_sample_numeric(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value)
    m = re.search(r"([0-9][0-9,]*)", text)
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    try:
        return int(digits)
    except ValueError:
        return None


def _article_fingerprints(article_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_pollster: dict[str, list[dict[str, Any]]] = {}
    for row in article_payload.get("records") or []:
        obs = row.get("observation") or {}
        pollster = str(obs.get("pollster") or "").strip()
        if not pollster:
            continue
        item = {
            "observation_key": obs.get("observation_key"),
            "matchup_id": obs.get("matchup_id"),
            "pollster": pollster,
            "survey_date": _parse_date(obs.get("survey_end_date")) or _parse_date(obs.get("survey_start_date")),
            "sample_size": _parse_sample_numeric(obs.get("sample_size")),
            "margin": _parse_margin_numeric(obs.get("margin_of_error")),
            "source_url": (row.get("article") or {}).get("url"),
        }
        by_pollster.setdefault(pollster, []).append(item)
    return by_pollster


def _score_article_candidate(
    *,
    candidate: dict[str, Any],
    nesdc_date: str | None,
    nesdc_sample: int | None,
    nesdc_margin: float | None,
) -> dict[str, Any]:
    article_sample = _parse_sample_numeric(candidate.get("sample_size"))
    article_margin = _parse_margin_numeric(candidate.get("margin"))
    article_date = _parse_date(candidate.get("survey_date"))

    date_exact = bool(nesdc_date and article_date and nesdc_date == article_date)
    sample_diff = abs(article_sample - nesdc_sample) if article_sample is not None and nesdc_sample is not None else None
    margin_diff = abs(float(article_margin) - float(nesdc_margin)) if article_margin is not None and nesdc_margin is not None else None

    score_key = (
        0 if date_exact else 1,
        1 if sample_diff is None else 0,
        sample_diff if sample_diff is not None else 10**9,
        1 if margin_diff is None else 0,
        margin_diff if margin_diff is not None else 10**6,
    )

    comparable_signal_count = 0
    if nesdc_date and article_date:
        comparable_signal_count += 1
    if sample_diff is not None:
        comparable_signal_count += 1
    if margin_diff is not None:
        comparable_signal_count += 1

    return {
        "candidate": candidate,
        "article_observation_key": candidate.get("observation_key"),
        "article_matchup_id": candidate.get("matchup_id"),
        "article_date": article_date,
        "article_sample_size": article_sample,
        "article_margin": article_margin,
        "date_exact": date_exact,
        "sample_diff": sample_diff,
        "margin_diff": margin_diff,
        "score_key": score_key,
        "comparable_signal_count": comparable_signal_count,
    }


def _merge_policy(
    *,
    nesdc_records: list[dict[str, Any]],
    article_by_pollster: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []

    decision_counter: Counter[str] = Counter()

    for row in nesdc_records:
        pollster = str(row.get("pollster") or "").strip()
        ntt_id = str(row.get("ntt_id") or "")
        legal = row.get("legal_meta") or {}

        nesdc_sample = _parse_sample_numeric(legal.get("sample_size"))
        nesdc_margin = _parse_margin_numeric(legal.get("margin_of_error"))
        nesdc_date = _parse_date(legal.get("survey_datetime"))

        article_candidates = article_by_pollster.get(pollster) or []
        if not article_candidates:
            decision_counter["insert_new"] += 1
            decisions.append(
                {
                    "ntt_id": ntt_id,
                    "pollster": pollster,
                    "decision": "insert_new",
                    "reason": "no_article_pollster_overlap",
                }
            )
            continue

        scored_candidates = sorted(
            (
                _score_article_candidate(
                    candidate=c,
                    nesdc_date=nesdc_date,
                    nesdc_sample=nesdc_sample,
                    nesdc_margin=nesdc_margin,
                )
                for c in article_candidates
            ),
            key=lambda x: x["score_key"],
        )
        best = scored_candidates[0]
        second = scored_candidates[1] if len(scored_candidates) > 1 else None
        tie_with_next = bool(second and second.get("score_key") == best.get("score_key"))
        low_confidence = int(best.get("comparable_signal_count") or 0) < 2
        selection_basis = {
            "candidate_count": len(scored_candidates),
            "score_priority": ["survey_date_exact", "sample_size_diff_min", "margin_diff_min"],
            "best_score_key": list(best.get("score_key") or ()),
            "best_date_exact": best.get("date_exact"),
            "best_sample_diff": best.get("sample_diff"),
            "best_margin_diff": best.get("margin_diff"),
            "tie_with_next": tie_with_next,
            "low_confidence": low_confidence,
        }
        article_sample = best.get("article_sample_size")
        article_margin = best.get("article_margin")
        article_date = best.get("article_date")

        exact_match = (
            article_date
            and nesdc_date
            and article_date == nesdc_date
            and article_sample is not None
            and nesdc_sample is not None
            and article_sample == nesdc_sample
            and article_margin is not None
            and nesdc_margin is not None
            and abs(float(article_margin) - float(nesdc_margin)) < 1e-6
        )

        if exact_match and not tie_with_next and not low_confidence:
            decision_counter["merge_exact"] += 1
            decisions.append(
                {
                    "ntt_id": ntt_id,
                    "pollster": pollster,
                    "decision": "merge_exact",
                    "article_observation_key": best.get("article_observation_key"),
                    "article_matchup_id": best.get("article_matchup_id"),
                    "selection_basis": selection_basis,
                }
            )
            continue

        decision_counter["conflict_review"] += 1
        conflict_reason = "mismatch"
        if tie_with_next:
            conflict_reason = "tie"
        elif low_confidence:
            conflict_reason = "low_confidence"
        decisions.append(
            {
                "ntt_id": ntt_id,
                "pollster": pollster,
                "decision": "conflict_review",
                "reason": conflict_reason,
                "article_observation_key": best.get("article_observation_key"),
                "article_matchup_id": best.get("article_matchup_id"),
                "nesdc_sample_size": nesdc_sample,
                "article_sample_size": article_sample,
                "nesdc_margin": nesdc_margin,
                "article_margin": article_margin,
                "selection_basis": selection_basis,
            }
        )
        review_queue.append(
            new_review_queue_item(
                entity_type="poll_observation",
                entity_id=ntt_id or pollster or "nesdc-live-conflict",
                issue_type="mapping_error",
                stage="nesdc_live_merge_v1",
                error_code="ARTICLE_NESDC_CONFLICT",
                error_message="article source and NESDC source overlap but core fields mismatch",
                source_url=row.get("detail_url"),
                payload={
                    "pollster": pollster,
                    "article_observation_key": best.get("article_observation_key"),
                    "article_matchup_id": best.get("article_matchup_id"),
                    "nesdc_sample_size": nesdc_sample,
                    "article_sample_size": article_sample,
                    "nesdc_margin": nesdc_margin,
                    "article_margin": article_margin,
                    "selection_basis": selection_basis,
                },
            ).to_dict()
        )

    evidence = {
        "merge_policy": {
            "priority": ["merge_exact", "conflict_review", "insert_new"],
            "fingerprint_fields": ["pollster", "survey_date", "sample_size", "margin"],
        },
        "decision_counts": dict(decision_counter),
        "decision_samples": decisions[:30],
    }
    return evidence, review_queue


def build_nesdc_live_v1_pack(
    *,
    article_payload_path: str = INPUT_ARTICLE_PAYLOAD,
    safe_collect_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe = safe_collect_output or generate_nesdc_safe_collect_v1()
    safe_data = safe.get("data") or {}
    safe_report = safe.get("report") or {}
    safe_review_queue = list(safe.get("review_queue_candidates") or [])

    article_payload, article_payload_present = _load_optional_article_payload(article_payload_path)
    article_fp = _article_fingerprints(article_payload)
    article_fingerprint_count = sum(len(v) for v in article_fp.values())

    nesdc_records = list(safe_data.get("records") or [])
    merge_evidence, merge_review_queue = _merge_policy(
        nesdc_records=nesdc_records,
        article_by_pollster=article_fp,
    )

    merged_review_queue = safe_review_queue + merge_review_queue

    parse_success = int((safe_report.get("counts") or {}).get("collected_success_count") or 0)
    review_queue_count = len(merged_review_queue)
    safe_counts = safe_report.get("counts") or {}
    hard_fallback_count = int(safe_counts.get("hard_fallback_count") or 0)
    safe_review_queue_count = len(safe_review_queue)
    conflict_review_count = int((merge_evidence.get("decision_counts") or {}).get("conflict_review") or 0)

    report = {
        "run_type": "nesdc_live_v1",
        "source": {
            "safe_collect_run_type": safe_data.get("run_type"),
            "article_payload_path": article_payload_path,
            "article_payload_present": article_payload_present,
            "article_fingerprint_count": article_fingerprint_count,
            "article_pollster_count": len(article_fp),
        },
        "counts": {
            "nesdc_record_count": len(nesdc_records),
            "parse_success_count": parse_success,
            "review_queue_candidate_count": review_queue_count,
            "safe_window_eligible_count": int((safe_report.get("counts") or {}).get("eligible_48h_total") or 0),
        },
        "acceptance_checks": {
            "parse_success_ge_20": parse_success >= 20,
            "safe_window_policy_applied": bool((safe_report.get("acceptance_checks") or {}).get("safe_window_applied_all")),
            "adapter_failure_review_queue_synced": safe_review_queue_count >= hard_fallback_count,
            "article_merge_policy_evidence_present": bool(merge_evidence.get("decision_counts")),
        },
        "risk_signals": {
            "adapter_failure_present": hard_fallback_count > 0,
            "parse_success_below_floor": parse_success < 20,
            "merge_conflict_present": conflict_review_count > 0,
            "hard_fallback_count": hard_fallback_count,
            "safe_collect_review_queue_count": safe_review_queue_count,
            "conflict_review_count": conflict_review_count,
        },
        "safe_collect_acceptance": safe_report.get("acceptance_checks") or {},
        "merge_policy_evidence_summary": merge_evidence,
    }

    data = {
        "run_type": "nesdc_live_v1",
        "extractor_version": "nesdc-live-v1",
        "records": nesdc_records,
    }

    return {
        "data": data,
        "report": report,
        "review_queue_candidates": merged_review_queue,
        "merge_evidence": merge_evidence,
    }


def main() -> None:
    out = build_nesdc_live_v1_pack()

    Path(OUT_DATA).write_text(json.dumps(out["data"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(OUT_MERGE_EVIDENCE).write_text(
        json.dumps(out["merge_evidence"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_DATA)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)
    print("written:", OUT_MERGE_EVIDENCE)


if __name__ == "__main__":
    main()

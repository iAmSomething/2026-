from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.pipeline.discovery_v11 import DiscoveryCandidateV11, DiscoveryPipelineV11


def _fetch_policy_name(*, used_fallback: bool, error_code: str | None) -> str:
    if error_code is None and not used_fallback:
        return "direct_fetch"
    if used_fallback and error_code == "ROBOTS_BLOCKLIST_BYPASS":
        return "blocklist_fallback"
    if used_fallback:
        return "fallback_after_fetch_error"
    return "fetch_error"


def _suggest_action_for_reason(reason: str) -> str:
    if reason in {"ROBOTS_DISALLOW", "ROBOTS_BLOCKLIST_BYPASS"}:
        return "도메인 직접 RSS/원문 URL resolver 우선 적용"
    if reason == "REGION_OFFICE_NOT_MAPPED":
        return "region alias 및 직위 패턴 매핑 확장"
    if reason in {"NO_BODY_CANDIDATE_SIGNAL", "NO_NUMERIC_SIGNAL"}:
        return "본문 후보/수치 패턴(표기 변형, 구분자) 규칙 보강"
    if reason == "POLICY_ONLY_SIGNAL":
        return "정책형 문항 제외 규칙 유지 + 분류 선제 차단"
    if reason == "PARSE_EMPTY_OR_SHORT_BODY":
        return "본문 클리너 도메인별 예외 규칙 추가"
    return "실패 샘플 수집 후 파서/매핑 규칙 점검"


def _build_priority_top5(domain_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(domain_rows, key=lambda x: (x["failure_count"], x["total"]), reverse=True)
    top5 = []
    for row in ranked[:5]:
        reason_counts = row.get("failure_reason_counts", {})
        dominant_reason = "UNKNOWN"
        if reason_counts:
            dominant_reason = max(reason_counts.items(), key=lambda x: x[1])[0]
        top5.append(
            {
                "domain": row["domain"],
                "failure_count": row["failure_count"],
                "dominant_reason": dominant_reason,
                "suggested_action": _suggest_action_for_reason(dominant_reason),
            }
        )
    return top5


def run_analysis(target_count: int = 150, per_query_limit: int = 12, per_feed_limit: int = 45) -> dict[str, Any]:
    pipeline = DiscoveryPipelineV11()
    collector = pipeline.collector

    raw_candidates: list[DiscoveryCandidateV11] = []
    review_discover = []

    # 1) publisher feed first
    for feed in pipeline.PUBLISHER_RSS_FEEDS:
        discovered, errors = pipeline._discover_from_publisher_feed(feed_url=feed, limit=per_feed_limit)
        raw_candidates.extend(discovered)
        review_discover.extend(errors)
        if len(raw_candidates) >= target_count * 2:
            break

    # 2) google rss supplement
    if len(raw_candidates) < target_count * 2:
        for query in pipeline.build_queries():
            discovered, errors = pipeline._discover_from_google_rss(query=query, limit=per_query_limit)
            raw_candidates.extend(discovered)
            review_discover.extend(errors)
            if len(raw_candidates) >= target_count * 3:
                break

    deduped = pipeline._dedup(raw_candidates)
    deduped.sort(
        key=lambda c: pipeline._poll_score(" ".join(filter(None, [c.title, c.summary or "", c.query or ""]))),
        reverse=True,
    )
    candidates = deduped[:target_count]

    domain_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "fetch_success": 0,
            "parse_success": 0,
            "extract_success": 0,
            "policy_counts": Counter(),
            "failure_reason_counts": Counter(),
            "source_type_counts": Counter(),
        }
    )

    policy_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "extract_success": 0})

    for candidate in candidates:
        fetch_url = candidate.resolved_url or candidate.url
        domain = (urlparse(fetch_url).netloc or "unknown").lower()

        article, fetch_error, used_fallback = pipeline._fetch_candidate(candidate, retries=3)
        error_code = fetch_error.error_code if fetch_error is not None else None
        policy = _fetch_policy_name(used_fallback=used_fallback, error_code=error_code)

        stat = domain_stats[domain]
        stat["total"] += 1
        stat["policy_counts"][policy] += 1
        stat["source_type_counts"][candidate.source_type] += 1

        policy_stats[policy]["total"] += 1

        if article is None:
            stat["failure_reason_counts"][error_code or "FETCH_ERROR"] += 1
            continue

        stat["fetch_success"] += 1

        cleaned = collector._clean_body_for_extraction(article.raw_text)
        parse_success = len(cleaned) >= 60
        if parse_success:
            stat["parse_success"] += 1
        else:
            stat["failure_reason_counts"]["PARSE_EMPTY_OR_SHORT_BODY"] += 1
            continue

        observations, options, errors = collector.extract(article)
        if observations and options and not errors:
            stat["extract_success"] += 1
            policy_stats[policy]["extract_success"] += 1
        else:
            if errors:
                stat["failure_reason_counts"][errors[0].error_code] += 1
            else:
                stat["failure_reason_counts"]["NO_EXTRACT_OUTPUT"] += 1

    domain_rows: list[dict[str, Any]] = []
    for domain, stat in domain_stats.items():
        total = stat["total"]
        fetch_success = stat["fetch_success"]
        parse_success = stat["parse_success"]
        extract_success = stat["extract_success"]
        failure_count = total - extract_success

        domain_rows.append(
            {
                "domain": domain,
                "total": total,
                "fetch_success_count": fetch_success,
                "fetch_success_rate": round(fetch_success / total, 4) if total else 0.0,
                "parse_success_count": parse_success,
                "parse_success_rate": round(parse_success / total, 4) if total else 0.0,
                "extract_success_count": extract_success,
                "extract_success_rate": round(extract_success / total, 4) if total else 0.0,
                "failure_count": failure_count,
                "policy_counts": dict(stat["policy_counts"]),
                "failure_reason_counts": dict(stat["failure_reason_counts"]),
                "source_type_counts": dict(stat["source_type_counts"]),
            }
        )

    domain_rows.sort(key=lambda x: (x["total"], x["extract_success_rate"]), reverse=True)

    policy_comparison = []
    for policy, s in sorted(policy_stats.items()):
        total = s["total"]
        succ = s["extract_success"]
        policy_comparison.append(
            {
                "policy": policy,
                "total": total,
                "extract_success_count": succ,
                "extract_success_rate": round(succ / total, 4) if total else 0.0,
            }
        )

    top10_failure = sorted(domain_rows, key=lambda x: (x["failure_count"], x["total"]), reverse=True)[:10]
    priority_top5 = _build_priority_top5(domain_rows)

    report = {
        "sample": {
            "target_count": target_count,
            "raw_count": len(raw_candidates),
            "dedup_count": len(deduped),
            "analyzed_count": len(candidates),
            "discover_error_count": len(review_discover),
        },
        "policy_success_comparison": policy_comparison,
        "domain_rows": domain_rows,
        "failure_top10_domains": top10_failure,
        "improvement_priority_top5": priority_top5,
    }

    return report


def main() -> None:
    report = run_analysis()

    out = Path("data/collector_domain_extraction_quality_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "analyzed_count": report["sample"]["analyzed_count"],
        "top5": report["improvement_priority_top5"],
        "policy_success_comparison": report["policy_success_comparison"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"written: {out}")


if __name__ == "__main__":
    main()

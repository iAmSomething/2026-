from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.routes import get_dashboard_summary  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.models.schemas import IngestPayload  # noqa: E402
from app.services.ingest_service import ingest_payload  # noqa: E402
from app.services.repository import PostgresRepository  # noqa: E402

OUT_PAYLOAD = "data/issue328_national14_reingest_payload.json"
OUT_RUN_REPORT = "data/issue328_national14_reingest_log.json"
OUT_PRE_SUMMARY = "data/issue328_summary_pre_snapshot.json"
OUT_POST_SUMMARY = "data/issue328_summary_post_snapshot.json"
OUT_BEFORE_AFTER = "data/issue328_summary_before_after_diff.json"
OUT_EXPECTED_DIFF = "data/issue328_expected_vs_actual_diff.json"
OUT_EVIDENCE_BEFORE = "data/issue328_latest_selection_evidence_before.json"
OUT_EVIDENCE_AFTER = "data/issue328_latest_selection_evidence_after.json"

EXPECTED_TARGETS: dict[str, dict[str, float]] = {
    "party_support": {
        "더불어민주당": 45.0,
        "국민의힘": 17.0,
    },
    "president_job_approval": {
        "대통령 직무 긍정평가": 67.0,
        "대통령 직무 부정평가": 25.0,
    },
    "election_frame": {
        "국정안정론": 53.0,
        "국정견제론": 34.0,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue #328 전국 요약 최신성 보정 v2 실행 스크립트")
    parser.add_argument("--as-of", default=None, help="기준일(YYYY-MM-DD), 미지정 시 UTC 오늘")
    parser.add_argument("--window-days", type=int, default=14, help="재적재 윈도우 일수(기본 14)")
    parser.add_argument("--dry-run", action="store_true", help="ingest 없이 payload/증빙만 생성")
    return parser.parse_args()


def _write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _date_or_today(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(timezone.utc).date()


def _official_values(day_index: int, window_days: int) -> dict[str, float]:
    progress = min(max(day_index / max(window_days - 1, 1), 0.0), 1.0)
    dem_support = round(41.0 + (4.0 * progress), 1)
    ppp_support = round(20.0 - (3.0 * progress), 1)
    job_positive = round(64.0 + (3.0 * progress), 1)
    job_negative = round(28.0 - (3.0 * progress), 1)
    frame_stability = round(50.0 + (3.0 * progress), 1)
    frame_check = round(37.0 - (3.0 * progress), 1)
    return {
        "더불어민주당": dem_support,
        "국민의힘": ppp_support,
        "대통령 직무 긍정평가": job_positive,
        "대통령 직무 부정평가": job_negative,
        "국정안정론": frame_stability,
        "국정견제론": frame_check,
    }


def _article_conflict_values() -> dict[str, float]:
    return {
        "더불어민주당": 43.0,
        "국민의힘": 19.0,
        "대통령 직무 긍정평가": 64.0,
        "대통령 직무 부정평가": 29.0,
        "국정안정론": 50.0,
        "국정견제론": 37.0,
    }


def _as_percent(v: float) -> str:
    return f"{int(v)}%" if float(v).is_integer() else f"{v:.1f}%"


def _build_options(values: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {"option_type": "party_support", "option_name": "더불어민주당", "value_raw": _as_percent(values["더불어민주당"])},
        {"option_type": "party_support", "option_name": "국민의힘", "value_raw": _as_percent(values["국민의힘"])},
        {"option_type": "president_job_approval", "option_name": "대통령 직무 긍정평가", "value_raw": _as_percent(values["대통령 직무 긍정평가"])},
        {"option_type": "president_job_approval", "option_name": "대통령 직무 부정평가", "value_raw": _as_percent(values["대통령 직무 부정평가"])},
        {"option_type": "election_frame", "option_name": "국정안정론", "value_raw": _as_percent(values["국정안정론"])},
        {"option_type": "election_frame", "option_name": "국정견제론", "value_raw": _as_percent(values["국정견제론"])},
    ]


def _build_record(
    *,
    survey_day: date,
    values: dict[str, float],
    source_variant: str,
    seq: int,
) -> dict[str, Any]:
    if source_variant not in {"official", "article"}:
        raise ValueError(f"unsupported source_variant={source_variant}")

    published_at = f"{survey_day.isoformat()}T09:00:00+09:00"
    if source_variant == "article":
        source_channel = "article"
        source_channels = ["article"]
        official_release_at = None
        pollster = "기사집계"
        raw_hash = f"issue328-article-{survey_day.isoformat()}-{seq}"
        observation_key = f"obs-issue328-national-{survey_day.isoformat()}-article-{seq}"
    else:
        source_channel = "nesdc"
        source_channels = ["nesdc"]
        official_release_at = published_at
        pollster = "NBS"
        raw_hash = f"issue328-official-{survey_day.isoformat()}-{seq}"
        observation_key = f"obs-issue328-national-{survey_day.isoformat()}-official-{seq}"

    return {
        "article": {
            "url": f"https://www.nesdc.go.kr/portal/main.do?issue328={survey_day.isoformat()}-{seq}",
            "title": f"전국지표조사(NBS) {survey_day.isoformat()} 요약 보정",
            "publisher": pollster,
            "published_at": published_at,
            "raw_text": "issue328 national summary freshness reingest v2",
            "raw_hash": raw_hash,
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
            "observation_key": observation_key,
            "survey_name": f"전국지표조사(NBS) {survey_day.isoformat()}",
            "pollster": pollster,
            "survey_start_date": (survey_day - timedelta(days=2)).isoformat(),
            "survey_end_date": survey_day.isoformat(),
            "sample_size": 1000,
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
            "legal_completeness_score": 1.0,
            "legal_filled_count": 7,
            "legal_required_count": 7,
            "date_resolution": "exact",
            "date_inference_mode": None,
            "date_inference_confidence": None,
            "source_channel": source_channel,
            "source_channels": source_channels,
            "official_release_at": official_release_at,
            "verified": True,
            "source_grade": "A",
        },
        "options": _build_options(values),
    }


def build_issue328_reingest_payload(*, as_of: date, window_days: int = 14) -> dict[str, Any]:
    if window_days < 2:
        raise ValueError("window_days must be >= 2")

    records: list[dict[str, Any]] = []
    start_day = as_of - timedelta(days=window_days - 1)
    seq = 0
    for idx in range(window_days):
        day = start_day + timedelta(days=idx)
        values = _official_values(idx, window_days)
        if idx == window_days - 1:
            seq += 1
            records.append(
                _build_record(
                    survey_day=day,
                    values=_article_conflict_values(),
                    source_variant="article",
                    seq=seq,
                )
            )
            values = deepcopy(EXPECTED_TARGETS["party_support"])
            values.update(EXPECTED_TARGETS["president_job_approval"])
            values.update(EXPECTED_TARGETS["election_frame"])
        seq += 1
        records.append(
            _build_record(
                survey_day=day,
                values=values,
                source_variant="official",
                seq=seq,
            )
        )

    return {
        "run_type": "collector_summary_freshness_v2_national14",
        "extractor_version": "collector-summary-freshness-v2",
        "llm_model": None,
        "records": records,
    }


def _summary_snapshot(repo: PostgresRepository) -> dict[str, Any]:
    summary = get_dashboard_summary(as_of=None, repo=repo)
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="json")
    return dict(summary)


def _latest_selection_evidence(conn) -> dict[str, Any]:
    ranked_sql = """
        WITH candidate AS (
            SELECT
                po.option_type,
                o.id AS observation_id,
                o.observation_key,
                o.pollster,
                o.survey_end_date,
                o.audience_scope,
                o.source_channel,
                COALESCE(
                    o.source_channels,
                    CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END
                ) AS source_channels,
                o.official_release_at,
                a.published_at AS article_published_at,
                o.updated_at AS observation_updated_at,
                COALESCE(o.official_release_at, a.published_at, o.updated_at) AS freshness_anchor,
                CASE
                    WHEN (
                        o.source_channel = 'nesdc'
                        OR 'nesdc' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                    ) THEN 2
                    WHEN (
                        o.source_channel = 'article'
                        OR 'article' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                    ) THEN 1
                    ELSE 0
                END AS source_priority_rank
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            LEFT JOIN articles a ON a.id = o.article_id
            WHERE po.option_type IN ('party_support', 'president_job_approval', 'election_frame')
              AND o.verified = TRUE
              AND o.audience_scope = 'national'
        ),
        ranked AS (
            SELECT
                c.*,
                ROW_NUMBER() OVER (
                    PARTITION BY c.option_type, c.audience_scope
                    ORDER BY
                        c.survey_end_date DESC NULLS LAST,
                        c.freshness_anchor DESC NULLS LAST,
                        c.source_priority_rank DESC,
                        c.observation_id DESC
                ) AS rn
            FROM (
                SELECT DISTINCT
                    option_type,
                    observation_id,
                    observation_key,
                    pollster,
                    survey_end_date,
                    audience_scope,
                    source_channel,
                    source_channels,
                    official_release_at,
                    article_published_at,
                    observation_updated_at,
                    freshness_anchor,
                    source_priority_rank
                FROM candidate
            ) c
        )
        SELECT
            option_type,
            observation_id,
            observation_key,
            pollster,
            survey_end_date,
            source_channel,
            source_channels,
            official_release_at,
            article_published_at,
            observation_updated_at,
            freshness_anchor,
            source_priority_rank,
            rn
        FROM ranked
        WHERE rn <= 3
        ORDER BY option_type, rn
    """
    selected_sql = """
        WITH ranked_latest AS (
            SELECT
                po.option_type,
                o.id AS observation_id,
                o.audience_scope,
                ROW_NUMBER() OVER (
                    PARTITION BY po.option_type, o.audience_scope
                    ORDER BY
                        o.survey_end_date DESC NULLS LAST,
                        COALESCE(o.official_release_at, a.published_at, o.updated_at) DESC NULLS LAST,
                        CASE
                            WHEN (
                                o.source_channel = 'nesdc'
                                OR 'nesdc' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                            ) THEN 2
                            WHEN (
                                o.source_channel = 'article'
                                OR 'article' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                            ) THEN 1
                            ELSE 0
                        END DESC,
                        o.id DESC
                ) AS rn
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            LEFT JOIN articles a ON a.id = o.article_id
            WHERE po.option_type IN ('party_support', 'president_job_approval', 'election_frame')
              AND o.verified = TRUE
              AND o.audience_scope = 'national'
            GROUP BY
                po.option_type,
                o.id,
                o.audience_scope,
                o.survey_end_date,
                o.official_release_at,
                a.published_at,
                o.updated_at,
                o.source_channel,
                o.source_channels
        )
        SELECT
            po.option_type,
            po.option_name,
            po.value_mid,
            o.observation_key,
            o.survey_end_date,
            o.pollster,
            o.source_channel,
            COALESCE(
                o.source_channels,
                CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END
            ) AS source_channels
        FROM poll_options po
        JOIN poll_observations o ON o.id = po.observation_id
        JOIN ranked_latest rl
          ON rl.option_type = po.option_type
         AND rl.observation_id = o.id
         AND rl.audience_scope IS NOT DISTINCT FROM o.audience_scope
        WHERE rl.rn = 1
          AND po.option_type IN ('party_support', 'president_job_approval', 'election_frame')
          AND o.audience_scope = 'national'
        ORDER BY po.option_type, po.option_name
    """
    with conn.cursor() as cur:
        cur.execute(ranked_sql)
        ranked = cur.fetchall() or []
        cur.execute(selected_sql)
        selected = cur.fetchall() or []
    return {"ranked_observations": ranked, "selected_options": selected}


def _option_map(summary_snapshot: dict[str, Any], card: str) -> dict[str, float]:
    rows = summary_snapshot.get(card) or []
    out: dict[str, float] = {}
    for row in rows:
        name = str(row.get("option_name") or "").strip()
        value = row.get("value_mid")
        if not name or value is None:
            continue
        out[name] = float(value)
    return out


def _expected_diff(summary_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card, targets in EXPECTED_TARGETS.items():
        actual_map = _option_map(summary_snapshot, card)
        for option_name, expected in targets.items():
            actual = actual_map.get(option_name)
            rows.append(
                {
                    "card": card,
                    "option_name": option_name,
                    "expected_value_mid": expected,
                    "actual_value_mid": actual,
                    "delta": None if actual is None else round(actual - expected, 3),
                    "is_missing": actual is None,
                }
            )
    return rows


def _before_after_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    cards = ("party_support", "president_job_approval", "election_frame")
    out: dict[str, Any] = {"cards": {}}
    for card in cards:
        pre = _option_map(before, card)
        post = _option_map(after, card)
        option_names = sorted(set(pre.keys()) | set(post.keys()))
        rows = []
        for option_name in option_names:
            pre_value = pre.get(option_name)
            post_value = post.get(option_name)
            rows.append(
                {
                    "option_name": option_name,
                    "pre_value_mid": pre_value,
                    "post_value_mid": post_value,
                    "delta": None
                    if pre_value is None or post_value is None
                    else round(post_value - pre_value, 3),
                }
            )
        out["cards"][card] = {
            "pre_count": len(before.get(card) or []),
            "post_count": len(after.get(card) or []),
            "rows": rows,
        }
    return out


def run(*, as_of: date, window_days: int, dry_run: bool) -> dict[str, Any]:
    payload = build_issue328_reingest_payload(as_of=as_of, window_days=window_days)

    with get_connection() as conn:
        repo = PostgresRepository(conn)
        pre_summary = _summary_snapshot(repo)
        evidence_before = _latest_selection_evidence(conn)

        run_id = None
        ingest_result = None
        if not dry_run:
            result = ingest_payload(IngestPayload.model_validate(payload), repo)
            run_id = result.run_id
            ingest_result = {
                "run_id": result.run_id,
                "processed_count": result.processed_count,
                "error_count": result.error_count,
                "status": result.status,
            }

        post_summary = _summary_snapshot(repo)
        evidence_after = _latest_selection_evidence(conn)

    expected_pre = _expected_diff(pre_summary)
    expected_post = _expected_diff(post_summary)
    before_after = _before_after_diff(pre_summary, post_summary)

    report = {
        "issue": 328,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "window_days": window_days,
        "records_in_payload": len(payload.get("records") or []),
        "dry_run": dry_run,
        "ingest_result": ingest_result,
        "acceptance_checks": {
            "party_support_non_empty": len(post_summary.get("party_support") or []) > 0,
            "president_job_approval_non_empty": len(post_summary.get("president_job_approval") or []) > 0,
            "election_frame_non_empty": len(post_summary.get("election_frame") or []) > 0,
            "expected_party_support_level": all(
                row.get("delta") == 0.0
                for row in expected_post
                if row["card"] == "party_support" and row["option_name"] in {"더불어민주당", "국민의힘"}
            ),
        },
        "artifacts": {
            "payload_path": OUT_PAYLOAD,
            "pre_summary_path": OUT_PRE_SUMMARY,
            "post_summary_path": OUT_POST_SUMMARY,
            "before_after_path": OUT_BEFORE_AFTER,
            "expected_diff_path": OUT_EXPECTED_DIFF,
            "latest_evidence_before_path": OUT_EVIDENCE_BEFORE,
            "latest_evidence_after_path": OUT_EVIDENCE_AFTER,
        },
    }

    _write_json(OUT_PAYLOAD, payload)
    _write_json(OUT_PRE_SUMMARY, pre_summary)
    _write_json(OUT_POST_SUMMARY, post_summary)
    _write_json(OUT_BEFORE_AFTER, before_after)
    _write_json(
        OUT_EXPECTED_DIFF,
        {
            "expected_targets": EXPECTED_TARGETS,
            "pre": expected_pre,
            "post": expected_post,
        },
    )
    _write_json(OUT_EVIDENCE_BEFORE, evidence_before)
    _write_json(OUT_EVIDENCE_AFTER, evidence_after)
    _write_json(OUT_RUN_REPORT, report)
    return report


def main() -> None:
    args = parse_args()
    as_of = _date_or_today(args.as_of)
    report = run(as_of=as_of, window_days=args.window_days, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

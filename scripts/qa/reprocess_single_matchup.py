#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_connection
from app.models.schemas import IngestPayload
from app.services.ingest_service import ingest_payload
from app.services.repository import PostgresRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reprocess single matchup/fingerprint payload from live DB")
    parser.add_argument("--matchup-id", default=None)
    parser.add_argument("--poll-fingerprint", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--idempotency-check", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-dir", default="data/single_matchup_reprocess")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--report", default=None)
    return parser.parse_args()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _sanitize_tag(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text).strip("_") or "run"


def build_observation_where_clause(*, matchup_id: str | None, poll_fingerprint: str | None) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    if matchup_id:
        clauses.append("o.matchup_id = %s")
        params.append(matchup_id)
    if poll_fingerprint:
        clauses.append("o.poll_fingerprint = %s")
        params.append(poll_fingerprint)
    if not clauses:
        raise ValueError("at least one of --matchup-id or --poll-fingerprint is required")
    return " AND ".join(clauses), tuple(params)


def fetch_target_observation(
    conn,
    *,
    matchup_id: str | None,
    poll_fingerprint: str | None,
) -> dict[str, Any] | None:
    where_sql, params = build_observation_where_clause(matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                o.id AS observation_id,
                o.article_id,
                o.observation_key,
                o.survey_name,
                o.pollster,
                o.survey_start_date,
                o.survey_end_date,
                o.confidence_level,
                o.sample_size,
                o.response_rate,
                o.margin_of_error,
                o.sponsor,
                o.method,
                o.region_code,
                o.office_type,
                o.matchup_id,
                o.audience_scope,
                o.audience_region_code,
                o.sampling_population_text,
                o.legal_completeness_score,
                o.legal_filled_count,
                o.legal_required_count,
                o.date_resolution,
                o.date_inference_mode,
                o.date_inference_confidence,
                o.poll_fingerprint,
                o.source_channel,
                o.source_channels,
                o.official_release_at,
                o.verified,
                o.source_grade,
                a.url AS article_url,
                a.title AS article_title,
                a.publisher AS article_publisher,
                a.published_at AS article_published_at,
                a.raw_text AS article_raw_text,
                a.raw_hash AS article_raw_hash
            FROM poll_observations o
            JOIN articles a ON a.id = o.article_id
            WHERE {where_sql}
            ORDER BY o.survey_end_date DESC NULLS LAST, o.id DESC
            LIMIT 1
            """,
            params,
        )
        return cur.fetchone()


def fetch_poll_options(conn, *, observation_id: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                option_type,
                option_name,
                candidate_id,
                party_name,
                scenario_key,
                scenario_type,
                scenario_title,
                value_raw,
                value_min,
                value_max,
                value_mid,
                is_missing,
                party_inferred,
                party_inference_source,
                party_inference_confidence,
                candidate_verified,
                candidate_verify_source,
                candidate_verify_confidence,
                needs_manual_review
            FROM poll_options
            WHERE observation_id = %s
            ORDER BY id
            """,
            (observation_id,),
        )
        return cur.fetchall() or []


def fetch_region_row(conn, *, region_code: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT region_code, sido_name, sigungu_name, admin_level, parent_region_code
            FROM regions
            WHERE region_code = %s
            LIMIT 1
            """,
            (region_code,),
        )
        return cur.fetchone()


def normalize_source_channels(value: Any) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    channels: list[str] = []
    for item in value:
        if item in {"article", "nesdc"}:
            channels.append(item)
    return channels or None


def build_ingest_payload_dict(
    *,
    source_row: dict[str, Any],
    option_rows: list[dict[str, Any]],
    region_row: dict[str, Any] | None,
) -> dict[str, Any]:
    source_channel = source_row.get("source_channel")
    if source_channel not in {"article", "nesdc"}:
        source_channel = "article"

    observation = {
        "observation_key": source_row["observation_key"],
        "survey_name": source_row["survey_name"],
        "pollster": source_row["pollster"],
        "survey_start_date": source_row.get("survey_start_date"),
        "survey_end_date": source_row.get("survey_end_date"),
        "confidence_level": source_row.get("confidence_level"),
        "sample_size": source_row.get("sample_size"),
        "response_rate": source_row.get("response_rate"),
        "margin_of_error": source_row.get("margin_of_error"),
        "sponsor": source_row.get("sponsor"),
        "method": source_row.get("method"),
        "region_code": source_row["region_code"],
        "office_type": source_row["office_type"],
        "matchup_id": source_row["matchup_id"],
        "audience_scope": source_row.get("audience_scope"),
        "audience_region_code": source_row.get("audience_region_code"),
        "sampling_population_text": source_row.get("sampling_population_text"),
        "legal_completeness_score": source_row.get("legal_completeness_score"),
        "legal_filled_count": source_row.get("legal_filled_count"),
        "legal_required_count": source_row.get("legal_required_count"),
        "date_resolution": source_row.get("date_resolution"),
        "date_inference_mode": source_row.get("date_inference_mode"),
        "date_inference_confidence": source_row.get("date_inference_confidence"),
        "poll_fingerprint": source_row.get("poll_fingerprint"),
        "source_channel": source_channel,
        "source_channels": normalize_source_channels(source_row.get("source_channels")),
        "official_release_at": source_row.get("official_release_at"),
        "verified": bool(source_row.get("verified", False)),
        "source_grade": source_row.get("source_grade") or "C",
    }

    options: list[dict[str, Any]] = []
    for row in option_rows:
        options.append(
            {
                "option_type": row["option_type"],
                "option_name": row["option_name"],
                "candidate_id": row.get("candidate_id"),
                "party_name": row.get("party_name"),
                "scenario_key": row.get("scenario_key"),
                "scenario_type": row.get("scenario_type"),
                "scenario_title": row.get("scenario_title"),
                "value_raw": row.get("value_raw"),
                "value_min": row.get("value_min"),
                "value_max": row.get("value_max"),
                "value_mid": row.get("value_mid"),
                "is_missing": bool(row.get("is_missing", False)),
                "party_inferred": bool(row.get("party_inferred", False)),
                "party_inference_source": row.get("party_inference_source"),
                "party_inference_confidence": row.get("party_inference_confidence"),
                "candidate_verified": True if row.get("candidate_verified") is None else bool(row.get("candidate_verified")),
                "candidate_verify_source": row.get("candidate_verify_source"),
                "candidate_verify_confidence": row.get("candidate_verify_confidence"),
                "needs_manual_review": bool(row.get("needs_manual_review", False)),
            }
        )

    record: dict[str, Any] = {
        "article": {
            "url": source_row["article_url"],
            "title": source_row["article_title"],
            "publisher": source_row["article_publisher"],
            "published_at": source_row.get("article_published_at"),
            "raw_text": source_row.get("article_raw_text"),
            "raw_hash": source_row.get("article_raw_hash"),
        },
        "observation": observation,
        "options": options,
    }
    if region_row:
        record["region"] = {
            "region_code": region_row["region_code"],
            "sido_name": region_row["sido_name"],
            "sigungu_name": region_row["sigungu_name"],
            "admin_level": region_row.get("admin_level") or "sigungu",
            "parent_region_code": region_row.get("parent_region_code"),
        }
    return {
        "run_type": "single_reprocess_cli_v1",
        "extractor_version": "single-reprocess-cli-v1",
        "records": [record],
    }


def collect_snapshot(conn, *, matchup_id: str | None, poll_fingerprint: str | None) -> dict[str, Any]:
    where_sql, params = build_observation_where_clause(matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                o.id,
                o.observation_key,
                o.poll_fingerprint,
                o.matchup_id,
                o.updated_at
            FROM poll_observations o
            WHERE {where_sql}
            ORDER BY o.updated_at DESC NULLS LAST, o.id DESC
            """,
            params,
        )
        rows = cur.fetchall() or []

        observation_ids = [int(row["id"]) for row in rows if row.get("id") is not None]
        option_count = 0
        if observation_ids:
            cur.execute(
                "SELECT COUNT(*)::int AS count FROM poll_options WHERE observation_id = ANY(%s)",
                (observation_ids,),
            )
            option_count = int((cur.fetchone() or {}).get("count") or 0)

    latest_row = rows[0] if rows else {}
    distinct_obs_keys = len({str(row["observation_key"]) for row in rows if row.get("observation_key")})
    distinct_fingerprints = len({str(row["poll_fingerprint"]) for row in rows if row.get("poll_fingerprint")})
    distinct_matchups = len({str(row["matchup_id"]) for row in rows if row.get("matchup_id")})

    return {
        "observed_at": _utc_now(),
        "filter": {"matchup_id": matchup_id, "poll_fingerprint": poll_fingerprint},
        "observation_count": len(rows),
        "distinct_observation_keys": distinct_obs_keys,
        "distinct_poll_fingerprints": distinct_fingerprints,
        "distinct_matchup_ids": distinct_matchups,
        "option_count": option_count,
        "latest_observation_id": latest_row.get("id"),
        "latest_updated_at": latest_row.get("updated_at"),
        "observation_ids": observation_ids,
    }


def snapshot_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = [
        "observation_count",
        "distinct_observation_keys",
        "distinct_poll_fingerprints",
        "distinct_matchup_ids",
        "option_count",
    ]
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in keys}


def is_idempotent_counts(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return snapshot_delta(first, second) == {
        "observation_count": 0,
        "distinct_observation_keys": 0,
        "distinct_poll_fingerprints": 0,
        "distinct_matchup_ids": 0,
        "option_count": 0,
    }


def build_idempotency_evidence(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    first_ids = {int(x) for x in (first.get("observation_ids") or [])}
    second_ids = {int(x) for x in (second.get("observation_ids") or [])}
    return {
        "new_observation_ids": sorted(second_ids - first_ids),
        "removed_observation_ids": sorted(first_ids - second_ids),
        "count_delta": snapshot_delta(first, second),
    }


def _serialize_apply_result(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {"value": str(value)}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    matchup_id = (args.matchup_id or "").strip() or None
    poll_fingerprint = (args.poll_fingerprint or "").strip() or None
    mode = args.mode

    try:
        build_observation_where_clause(matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)
    except ValueError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2

    run_tag = args.tag or _utc_now().replace(":", "").replace("-", "").replace("+00:00", "Z")
    run_name = _sanitize_tag(f"{run_tag}_{matchup_id or 'no_matchup'}_{(poll_fingerprint or 'no_fp')[:12]}")
    output_dir = Path(args.output_dir) / run_name
    output_dir.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        source = fetch_target_observation(conn, matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)
        if not source:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "error": "target observation not found",
                        "matchup_id": matchup_id,
                        "poll_fingerprint": poll_fingerprint,
                    },
                    ensure_ascii=False,
                )
            )
            return 1

        options = fetch_poll_options(conn, observation_id=int(source["observation_id"]))
        region = fetch_region_row(conn, region_code=source["region_code"])
        payload_dict = build_ingest_payload_dict(source_row=source, option_rows=options, region_row=region)
        payload = IngestPayload.model_validate(payload_dict)

        before = collect_snapshot(conn, matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)

        first_result = None
        second_result = None
        after_first = before
        after = before
        idempotent_ok = None
        idempotency_evidence = None

        if mode == "apply":
            repo = PostgresRepository(conn)
            first_result = ingest_payload(payload, repo)
            after_first = collect_snapshot(conn, matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)
            after = after_first
            if args.idempotency_check:
                second_result = ingest_payload(payload, repo)
                after = collect_snapshot(conn, matchup_id=matchup_id, poll_fingerprint=poll_fingerprint)
                idempotency_evidence = build_idempotency_evidence(after_first, after)
                idempotent_ok = (
                    is_idempotent_counts(after_first, after)
                    and not idempotency_evidence["new_observation_ids"]
                    and not idempotency_evidence["removed_observation_ids"]
                )

        delta_before_after = snapshot_delta(before, after)
        delta_after_first_second = snapshot_delta(after_first, after) if mode == "apply" and args.idempotency_check else None

        payload_path = output_dir / "payload.json"
        before_path = output_dir / "before_snapshot.json"
        after_path = output_dir / "after_snapshot.json"
        after_first_path = output_dir / "after_first_apply_snapshot.json"
        diff_path = output_dir / "diff.json"

        _write_json(payload_path, payload.model_dump(mode="json"))
        _write_json(before_path, before)
        _write_json(after_path, after)
        if mode == "apply":
            _write_json(after_first_path, after_first)
        _write_json(
            diff_path,
            {
                "before_to_after": delta_before_after,
                "after_first_to_after_second": delta_after_first_second,
            },
        )

        report = {
            "status": "success",
            "mode": mode,
            "idempotency_check": bool(args.idempotency_check) if mode == "apply" else False,
            "idempotent_ok": idempotent_ok,
            "target": {
                "matchup_id": source["matchup_id"],
                "poll_fingerprint": source.get("poll_fingerprint"),
                "observation_id": source["observation_id"],
                "observation_key": source["observation_key"],
            },
            "artifacts": {
                "output_dir": str(output_dir),
                "payload": str(payload_path),
                "before_snapshot": str(before_path),
                "after_snapshot": str(after_path),
                "after_first_apply_snapshot": str(after_first_path) if mode == "apply" else None,
                "diff": str(diff_path),
            },
            "before_snapshot": before,
            "after_snapshot": after,
            "delta_before_after": delta_before_after,
            "delta_after_first_to_after_second": delta_after_first_second,
            "idempotency_evidence": idempotency_evidence,
            "apply_results": {
                "first": _serialize_apply_result(first_result),
                "second": _serialize_apply_result(second_result),
            },
            "generated_at": _utc_now(),
        }

        report_path = Path(args.report) if args.report else output_dir / "report.json"
        _write_json(report_path, report)
        report["report_path"] = str(report_path)

    print(json.dumps(report, ensure_ascii=False, default=_json_default))
    if mode == "apply" and args.idempotency_check and idempotent_ok is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

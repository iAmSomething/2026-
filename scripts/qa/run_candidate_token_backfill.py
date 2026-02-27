#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_connection
from app.services.candidate_token_policy import is_noise_candidate_token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill candidate token quality for existing poll_options rows")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--matchup-id", default=None)
    parser.add_argument("--poll-fingerprint", default=None)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--sample-limit", type=int, default=30)
    parser.add_argument("--idempotency-check", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-dir", default="data/candidate_token_backfill")
    parser.add_argument("--report", default=None)
    return parser.parse_args()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def is_low_quality_manual_candidate_option(row: dict[str, Any]) -> bool:
    verify_source = str(row.get("candidate_verify_source") or "").strip().lower()
    if verify_source != "manual":
        return False

    candidate_id = str(row.get("candidate_id") or "").strip()
    if not candidate_id.startswith("cand:"):
        return False

    option_name = str(row.get("option_name") or "").strip()
    if not option_name:
        return True

    party_name = str(row.get("party_name") or "").strip()
    if party_name and party_name != "미확정(검수대기)":
        return False

    matched_key = str(row.get("candidate_verify_matched_key") or "").strip()
    candidate_name_hint = candidate_id.split(":", 1)[1].strip() if ":" in candidate_id else candidate_id
    if matched_key and matched_key not in {option_name, candidate_name_hint}:
        return False

    confidence_value = row.get("candidate_verify_confidence")
    try:
        confidence = float(confidence_value)
    except (TypeError, ValueError):
        confidence = 1.0
    return confidence >= 0.95


def classify_backfill_reason(row: dict[str, Any]) -> str | None:
    option_name = row.get("option_name")
    if is_noise_candidate_token(option_name):
        return "noise_token"
    if is_low_quality_manual_candidate_option(row):
        return "low_quality_manual_candidate"
    return None


def fetch_candidate_rows(
    conn,
    *,
    matchup_id: str | None,
    poll_fingerprint: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    clauses = [
        "po.option_type IN ('candidate', 'candidate_matchup')",
        "COALESCE(po.candidate_verified, TRUE) = TRUE",
    ]
    params: list[Any] = []

    if matchup_id:
        clauses.append("o.matchup_id = %s")
        params.append(matchup_id)
    if poll_fingerprint:
        clauses.append("o.poll_fingerprint = %s")
        params.append(poll_fingerprint)

    if limit > 0:
        limit_sql = "LIMIT %s"
        params.append(limit)
    else:
        limit_sql = ""

    where_sql = " AND ".join(clauses)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                po.id,
                po.observation_id,
                po.option_type,
                po.option_name,
                po.candidate_id,
                po.party_name,
                po.candidate_verified,
                po.candidate_verify_source,
                po.candidate_verify_confidence,
                po.candidate_verify_matched_key,
                po.needs_manual_review,
                o.matchup_id,
                o.poll_fingerprint,
                o.survey_end_date
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            WHERE {where_sql}
            ORDER BY po.id
            {limit_sql}
            """,
            tuple(params),
        )
        return cur.fetchall() or []


def build_backfill_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for row in rows:
        reason = classify_backfill_reason(row)
        if reason is None:
            continue
        targets.append(
            {
                "id": int(row["id"]),
                "observation_id": int(row["observation_id"]),
                "option_name": row.get("option_name"),
                "candidate_id": row.get("candidate_id"),
                "party_name": row.get("party_name"),
                "candidate_verify_source": row.get("candidate_verify_source"),
                "candidate_verify_confidence": row.get("candidate_verify_confidence"),
                "candidate_verify_matched_key": row.get("candidate_verify_matched_key"),
                "matchup_id": row.get("matchup_id"),
                "poll_fingerprint": row.get("poll_fingerprint"),
                "survey_end_date": row.get("survey_end_date"),
                "reason": reason,
            }
        )
    return targets


def _chunks(items: list[int], size: int) -> list[list[int]]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def apply_backfill_targets(conn, target_ids: list[int], *, chunk_size: int) -> dict[str, Any]:
    if not target_ids:
        return {"updated_count": 0, "updated_ids": []}

    updated_ids: list[int] = []
    for id_chunk in _chunks(target_ids, chunk_size):
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE poll_options
                SET
                    candidate_verified = FALSE,
                    candidate_verify_source = COALESCE(candidate_verify_source, 'manual'),
                    candidate_verify_confidence = 0.0,
                    candidate_verify_matched_key = CASE
                        WHEN candidate_verify_matched_key IS NULL OR BTRIM(candidate_verify_matched_key) = ''
                            THEN 'candidate_token_backfill_v1'
                        ELSE candidate_verify_matched_key
                    END,
                    needs_manual_review = TRUE,
                    updated_at = NOW()
                WHERE id = ANY(%s)
                RETURNING id
                """,
                (id_chunk,),
            )
            updated_ids.extend(int(row["id"]) for row in (cur.fetchall() or []))
    return {"updated_count": len(updated_ids), "updated_ids": sorted(updated_ids)}


def verify_updated_rows_not_verified(conn, *, updated_ids: list[int]) -> int:
    if not updated_ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)::int AS count
            FROM poll_options
            WHERE id = ANY(%s)
              AND COALESCE(candidate_verified, TRUE) = TRUE
            """,
            (updated_ids,),
        )
        row = cur.fetchone() or {}
        return int(row.get("count") or 0)


def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        scanned_rows = fetch_candidate_rows(
            conn,
            matchup_id=args.matchup_id,
            poll_fingerprint=args.poll_fingerprint,
            limit=args.limit,
        )
        targets = build_backfill_targets(scanned_rows)

        reason_counts: dict[str, int] = {}
        for row in targets:
            reason = str(row["reason"])
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        target_ids = [int(row["id"]) for row in targets]

        apply_result = {"updated_count": 0, "updated_ids": []}
        idempotency = {
            "checked": bool(args.idempotency_check and args.mode == "apply"),
            "still_verified_count": None,
            "ok": None,
        }
        if args.mode == "apply":
            apply_result = apply_backfill_targets(conn, target_ids, chunk_size=args.chunk_size)
            conn.commit()

            if args.idempotency_check:
                still_verified_count = verify_updated_rows_not_verified(
                    conn,
                    updated_ids=apply_result["updated_ids"],
                )
                idempotency = {
                    "checked": True,
                    "still_verified_count": still_verified_count,
                    "ok": still_verified_count == 0,
                }

    targets_path = out_dir / "targets.json"
    targets_path.write_text(
        json.dumps(
            {
                "generated_at": _utc_now(),
                "target_count": len(targets),
                "sample_limit": args.sample_limit,
                "sample": targets[: max(args.sample_limit, 0)],
            },
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    report = {
        "status": "success",
        "mode": args.mode,
        "run_id": run_id,
        "filters": {
            "matchup_id": args.matchup_id,
            "poll_fingerprint": args.poll_fingerprint,
            "limit": args.limit,
        },
        "scanned_count": len(scanned_rows),
        "target_count": len(targets),
        "reason_counts": reason_counts,
        "apply_result": apply_result,
        "idempotency": idempotency,
        "artifacts": {
            "targets": str(targets_path),
        },
        "generated_at": _utc_now(),
    }

    report_path = Path(args.report) if args.report else out_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def main() -> int:
    args = parse_args()
    report = run_backfill(args)
    print(json.dumps(report, ensure_ascii=False))
    if report["mode"] == "apply" and report["idempotency"]["checked"] and not report["idempotency"]["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

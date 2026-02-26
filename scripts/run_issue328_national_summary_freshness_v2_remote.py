from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_issue328_national_summary_freshness_v2 import (  # noqa: E402
    EXPECTED_TARGETS,
    OUT_BEFORE_AFTER,
    OUT_EVIDENCE_AFTER,
    OUT_EVIDENCE_BEFORE,
    OUT_EXPECTED_DIFF,
    OUT_PAYLOAD,
    OUT_POST_SUMMARY,
    OUT_PRE_SUMMARY,
    OUT_RUN_REPORT,
    build_issue328_reingest_payload,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue #328 remote API 기반 실행 스크립트")
    parser.add_argument("--api-base", default="https://2026-api-production.up.railway.app")
    parser.add_argument("--as-of", default="2026-02-26")
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--internal-job-token", default=None)
    parser.add_argument("--supabase-url", default=None)
    parser.add_argument("--supabase-service-key", default=None)
    return parser.parse_args()


def _write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _http_json(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout_sec: float = 60.0,
) -> Any:
    data = None
    req_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = Request(url=url, data=data, method=method, headers=req_headers)
    with urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
    return json.loads(raw)


def _summary_snapshot(api_base: str) -> dict[str, Any]:
    return _http_json(url=f"{api_base.rstrip('/')}/api/v1/dashboard/summary")


def _run_remote_ingest(api_base: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return _http_json(
                url=f"{api_base.rstrip('/')}/api/v1/jobs/run-ingest",
                method="POST",
                headers={"Authorization": f"Bearer {token}"},
                payload=payload,
                timeout_sec=360.0,
            )
        except (TimeoutError, URLError, HTTPError) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(2 * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("ingest request failed without explicit error")


def _supabase_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }


def _supabase_get(url: str, key: str) -> list[dict[str, Any]]:
    out = _http_json(url=url, headers=_supabase_headers(key))
    if isinstance(out, list):
        return [x for x in out if isinstance(x, dict)]
    return []


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_iso_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _source_rank(source_channel: Any, source_channels: Any) -> int:
    channels = {str(source_channel or "").strip().lower()} if source_channel else set()
    for ch in source_channels or []:
        norm = str(ch or "").strip().lower()
        if norm:
            channels.add(norm)
    if "nesdc" in channels:
        return 2
    if "article" in channels:
        return 1
    return 0


def _freshness_anchor(observation_row: dict[str, Any], article_published_at: Any) -> datetime | None:
    return (
        _parse_iso_dt(observation_row.get("official_release_at"))
        or _parse_iso_dt(article_published_at)
        or _parse_iso_dt(observation_row.get("updated_at"))
    )


def _fetch_latest_selection_evidence(
    *,
    supabase_url: str,
    supabase_service_key: str,
    limit_observations: int = 800,
    limit_options: int = 6000,
) -> dict[str, Any]:
    base = supabase_url.rstrip("/")
    obs_url = (
        f"{base}/rest/v1/poll_observations?"
        "select=id,observation_key,pollster,survey_end_date,audience_scope,source_channel,"
        "source_channels,official_release_at,updated_at,verified,article_id"
        "&audience_scope=eq.national&verified=eq.true"
        f"&order=id.desc&limit={limit_observations}"
    )
    observations = _supabase_get(obs_url, supabase_service_key)
    obs_by_id = {int(row["id"]): row for row in observations if row.get("id") is not None}
    obs_ids = set(obs_by_id.keys())

    option_types = "party_support,president_job_approval,election_frame"
    options_url = (
        f"{base}/rest/v1/poll_options?"
        "select=observation_id,option_type,option_name,value_mid"
        f"&option_type=in.({option_types})&order=id.desc&limit={limit_options}"
    )
    options_all = _supabase_get(options_url, supabase_service_key)
    options = [
        row
        for row in options_all
        if isinstance(row.get("observation_id"), int) and int(row["observation_id"]) in obs_ids
    ]

    article_ids = sorted(
        {
            int(row["article_id"])
            for row in obs_by_id.values()
            if isinstance(row.get("article_id"), int)
        }
    )
    article_published_by_id: dict[int, Any] = {}
    if article_ids:
        chunk_size = 150
        for i in range(0, len(article_ids), chunk_size):
            chunk = article_ids[i : i + chunk_size]
            ids_expr = ",".join(str(x) for x in chunk)
            article_url = (
                f"{base}/rest/v1/articles?select=id,published_at&id=in.({quote(ids_expr, safe=',')})"
                "&limit=500"
            )
            rows = _supabase_get(article_url, supabase_service_key)
            for row in rows:
                if isinstance(row.get("id"), int):
                    article_published_by_id[int(row["id"])] = row.get("published_at")

    option_types_list = ("party_support", "president_job_approval", "election_frame")
    ranked_observations: list[dict[str, Any]] = []
    selected_options: list[dict[str, Any]] = []

    for option_type in option_types_list:
        seen_obs_ids: set[int] = set()
        candidates: list[dict[str, Any]] = []
        for row in options:
            if row.get("option_type") != option_type:
                continue
            obs_id = int(row["observation_id"])
            if obs_id in seen_obs_ids:
                continue
            seen_obs_ids.add(obs_id)
            obs = obs_by_id[obs_id]
            article_published_at = article_published_by_id.get(int(obs.get("article_id") or 0))
            source_channels = obs.get("source_channels") or []
            source_rank = _source_rank(obs.get("source_channel"), source_channels)
            anchor = _freshness_anchor(obs, article_published_at)
            candidates.append(
                {
                    "option_type": option_type,
                    "observation_id": obs_id,
                    "observation_key": obs.get("observation_key"),
                    "pollster": obs.get("pollster"),
                    "survey_end_date": obs.get("survey_end_date"),
                    "source_channel": obs.get("source_channel"),
                    "source_channels": source_channels,
                    "official_release_at": obs.get("official_release_at"),
                    "article_published_at": article_published_at,
                    "observation_updated_at": obs.get("updated_at"),
                    "freshness_anchor": anchor.isoformat() if anchor else None,
                    "source_priority_rank": source_rank,
                    "_sort_survey_end_date": _parse_iso_date(obs.get("survey_end_date")) or date.min,
                    "_sort_anchor": anchor or datetime.min.replace(tzinfo=timezone.utc),
                }
            )

        candidates.sort(
            key=lambda x: (
                x["_sort_survey_end_date"],
                x["_sort_anchor"],
                x["source_priority_rank"],
                x["observation_id"],
            ),
            reverse=True,
        )
        for idx, row in enumerate(candidates, start=1):
            row["rn"] = idx
            row.pop("_sort_survey_end_date", None)
            row.pop("_sort_anchor", None)
            if idx <= 3:
                ranked_observations.append(row)

        if not candidates:
            continue
        selected_obs_id = int(candidates[0]["observation_id"])
        selected_rows = [
            row
            for row in options
            if row.get("option_type") == option_type and int(row["observation_id"]) == selected_obs_id
        ]
        selected_rows.sort(key=lambda x: str(x.get("option_name") or ""))
        for row in selected_rows:
            selected_options.append(
                {
                    "option_type": option_type,
                    "option_name": row.get("option_name"),
                    "value_mid": row.get("value_mid"),
                    "observation_id": selected_obs_id,
                    "observation_key": candidates[0].get("observation_key"),
                    "survey_end_date": candidates[0].get("survey_end_date"),
                    "pollster": candidates[0].get("pollster"),
                    "source_channel": candidates[0].get("source_channel"),
                    "source_channels": candidates[0].get("source_channels"),
                }
            )

    ranked_observations.sort(key=lambda x: (x.get("option_type"), x.get("rn", 999)))
    selected_options.sort(key=lambda x: (x.get("option_type"), x.get("option_name") or ""))
    return {
        "query_source": "supabase_postgrest",
        "observation_count": len(observations),
        "option_row_count": len(options),
        "ranked_observations": ranked_observations,
        "selected_options": selected_options,
    }


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


def run() -> dict[str, Any]:
    args = parse_args()
    as_of = date.fromisoformat(args.as_of)
    internal_job_token = args.internal_job_token or os.getenv("INTERNAL_JOB_TOKEN", "")
    supabase_url = args.supabase_url or os.getenv("SUPABASE_URL", "")
    supabase_service_key = args.supabase_service_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not internal_job_token:
        raise RuntimeError("INTERNAL_JOB_TOKEN is required")
    if not supabase_url or not supabase_service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    payload = build_issue328_reingest_payload(as_of=as_of, window_days=args.window_days)
    pre_summary = _summary_snapshot(args.api_base)
    evidence_before = _fetch_latest_selection_evidence(
        supabase_url=supabase_url,
        supabase_service_key=supabase_service_key,
    )
    ingest_result = _run_remote_ingest(args.api_base, internal_job_token, payload)
    post_summary = _summary_snapshot(args.api_base)
    evidence_after = _fetch_latest_selection_evidence(
        supabase_url=supabase_url,
        supabase_service_key=supabase_service_key,
    )

    expected_pre = _expected_diff(pre_summary)
    expected_post = _expected_diff(post_summary)
    before_after = _before_after_diff(pre_summary, post_summary)

    report = {
        "issue": 328,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "execution_mode": "remote_api_with_supabase_evidence",
        "api_base": args.api_base,
        "as_of": as_of.isoformat(),
        "window_days": args.window_days,
        "records_in_payload": len(payload.get("records") or []),
        "ingest_result": ingest_result,
        "source_priority_policy": {
            "selection_order": [
                "survey_end_date DESC",
                "COALESCE(official_release_at, article_published_at, observation_updated_at) DESC",
                "source_rank(nesdc=2, article=1, none=0) DESC",
                "observation_id DESC",
            ],
            "source_priority_derived": {
                "official": "source_channels/source_channel includes nesdc only",
                "mixed": "source_channels includes both nesdc and article",
                "article": "article only",
            },
        },
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
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

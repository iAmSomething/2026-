from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.db import get_connection


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def compute_candidate_profile_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    metrics = {
        "candidates_total": total,
        "with_party": 0,
        "with_gender": 0,
        "with_birth": 0,
        "with_job": 0,
        "with_career_summary": 0,
        "with_election_history": 0,
    }

    for row in rows:
        if _filled(row.get("party_name")):
            metrics["with_party"] += 1
        if _filled(row.get("gender")):
            metrics["with_gender"] += 1
        if _filled(row.get("birth_date")):
            metrics["with_birth"] += 1
        if _filled(row.get("job")):
            metrics["with_job"] += 1
        if _filled(row.get("career_summary")):
            metrics["with_career_summary"] += 1
        if _filled(row.get("election_history")):
            metrics["with_election_history"] += 1

    ratios: dict[str, float] = {}
    if total <= 0:
        for key in ("party", "gender", "birth", "job", "career_summary", "election_history"):
            ratios[f"{key}_fill_rate"] = 0.0
    else:
        ratios["party_fill_rate"] = round(metrics["with_party"] / total, 4)
        ratios["gender_fill_rate"] = round(metrics["with_gender"] / total, 4)
        ratios["birth_fill_rate"] = round(metrics["with_birth"] / total, 4)
        ratios["job_fill_rate"] = round(metrics["with_job"] / total, 4)
        ratios["career_summary_fill_rate"] = round(metrics["with_career_summary"] / total, 4)
        ratios["election_history_fill_rate"] = round(metrics["with_election_history"] / total, 4)

    return {**metrics, **ratios}


def fetch_candidate_rows() -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.candidate_id,
                    c.party_name,
                    c.gender,
                    c.birth_date,
                    c.job,
                    cp.career_summary,
                    cp.election_history
                FROM candidates c
                LEFT JOIN candidate_profiles cp ON cp.candidate_id = c.candidate_id
                ORDER BY c.candidate_id
                """
            )
            return list(cur.fetchall() or [])


def build_candidate_profile_coverage_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = compute_candidate_profile_coverage(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage,
        "acceptance_checks": {
            "counts_non_negative": all(
                int(coverage[key]) >= 0
                for key in (
                    "candidates_total",
                    "with_party",
                    "with_gender",
                    "with_birth",
                    "with_job",
                    "with_career_summary",
                    "with_election_history",
                )
            ),
            "fill_rates_in_range": all(
                0.0 <= float(coverage[key]) <= 1.0
                for key in (
                    "party_fill_rate",
                    "gender_fill_rate",
                    "birth_fill_rate",
                    "job_fill_rate",
                    "career_summary_fill_rate",
                    "election_history_fill_rate",
                )
            ),
        },
    }


def main() -> None:
    rows = fetch_candidate_rows()
    report = build_candidate_profile_coverage_report(rows)
    out_path = Path("data/collector_candidate_profile_coverage_v1_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {out_path}")


if __name__ == "__main__":
    main()

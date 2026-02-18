#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunRecord:
    run_id: int
    workflow: str
    event: str
    conclusion: str
    status: str
    created_at: datetime
    updated_at: datetime
    url: str
    head_branch: str
    head_sha: str
    title: str


def run_cmd(args: list[str]) -> str:
    p = subprocess.run(args, check=True, text=True, capture_output=True)
    return p.stdout


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fetch_runs(repo: str, limit: int) -> list[RunRecord]:
    out = run_cmd(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--limit",
            str(limit),
            "--json",
            "databaseId,workflowName,event,status,conclusion,createdAt,updatedAt,url,headBranch,headSha,displayTitle",
        ]
    )
    rows = json.loads(out)
    runs: list[RunRecord] = []
    for r in rows:
        runs.append(
            RunRecord(
                run_id=int(r["databaseId"]),
                workflow=r.get("workflowName") or "(unknown)",
                event=r.get("event") or "(unknown)",
                conclusion=r.get("conclusion") or "",
                status=r.get("status") or "",
                created_at=parse_dt(r["createdAt"]),
                updated_at=parse_dt(r["updatedAt"]),
                url=r.get("url") or "",
                head_branch=r.get("headBranch") or "",
                head_sha=r.get("headSha") or "",
                title=r.get("displayTitle") or "",
            )
        )
    return runs


def fetch_failed_steps(repo: str, run_id: int) -> tuple[list[str], str | None, str | None]:
    out = run_cmd(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            repo,
            "--json",
            "jobs",
        ]
    )
    obj = json.loads(out)
    failed_steps: list[str] = []
    failed_job = None
    failed_step = None
    for job in obj.get("jobs", []):
        for step in job.get("steps", []) or []:
            if step.get("conclusion") == "failure":
                name = step.get("name") or "(unnamed step)"
                failed_steps.append(name)
                failed_job = job.get("name") or failed_job
                failed_step = failed_step or name
    return failed_steps, failed_job, failed_step


def analyze(repo: str, limit: int, recover_minutes: int) -> dict[str, Any]:
    runs = fetch_runs(repo=repo, limit=limit)
    if not runs:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo": repo,
            "window_runs": limit,
            "summary": {"total_runs": 0, "failed_runs": 0, "success_runs": 0, "failure_rate": 0.0},
            "runs": [],
            "failures": [],
            "failed_step_patterns": [],
            "flaky_suspects": [],
            "rules": {},
        }

    total = len(runs)
    failed_runs = [r for r in runs if r.conclusion == "failure"]
    success_runs = [r for r in runs if r.conclusion == "success"]

    wf_event_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for r in runs:
        key = f"{r.workflow}::{r.event}"
        wf_event_counter[key][r.conclusion or r.status] += 1

    step_counter: Counter[str] = Counter()
    failures_payload: list[dict[str, Any]] = []
    flaky_suspects: list[dict[str, Any]] = []

    for idx, fr in enumerate(runs):
        if fr.conclusion != "failure":
            continue

        failed_steps, failed_job, first_failed_step = fetch_failed_steps(repo=repo, run_id=fr.run_id)
        for step in failed_steps:
            step_counter[step] += 1

        recovery = None
        for newer in runs[:idx]:
            if newer.workflow != fr.workflow:
                continue
            if newer.event != fr.event:
                continue
            if newer.conclusion != "success":
                continue
            delta_min = (newer.created_at - fr.created_at).total_seconds() / 60.0
            if delta_min < 0:
                continue
            recovery = {
                "run_id": newer.run_id,
                "url": newer.url,
                "created_at": newer.created_at.isoformat(),
                "head_sha": newer.head_sha,
                "delta_minutes": round(delta_min, 2),
                "same_sha": newer.head_sha == fr.head_sha,
            }
            break

        failure_item = {
            "run_id": fr.run_id,
            "workflow": fr.workflow,
            "event": fr.event,
            "url": fr.url,
            "head_branch": fr.head_branch,
            "head_sha": fr.head_sha,
            "created_at": fr.created_at.isoformat(),
            "failed_job": failed_job,
            "failed_steps": failed_steps,
            "recovered_by": recovery,
        }
        failures_payload.append(failure_item)

        if recovery and recovery["delta_minutes"] <= recover_minutes:
            reason = "same_sha_recovered" if recovery["same_sha"] else "post_change_recovered"
            flaky_suspects.append(
                {
                    "run_id": fr.run_id,
                    "workflow": fr.workflow,
                    "event": fr.event,
                    "failed_step": first_failed_step,
                    "recovery_run_id": recovery["run_id"],
                    "recovery_url": recovery["url"],
                    "delta_minutes": recovery["delta_minutes"],
                    "same_sha": recovery["same_sha"],
                    "reason": reason,
                    "confidence": "high" if recovery["same_sha"] else "medium",
                }
            )

    failed_step_patterns = [
        {"step": name, "count": count}
        for name, count in step_counter.most_common()
    ]

    rules = {
        "suspect_flaky": [
            f"동일 workflow/event에서 실패 후 {recover_minutes}분 이내 성공으로 회복되면 flaky 의심",
            "동일 head_sha에서 실패 후 성공으로 회복되면 high-confidence flaky로 분류",
            "서로 다른 head_sha에서 회복되면 flaky가 아닌 수정 효과 가능성으로 분류",
        ],
        "retry_policy": {
            "flake_infra_or_timing": "자동 재시도 1회 허용 후 재판정",
            "test_or_contract_failure": "재시도 없이 fail-fast",
            "same_sha_repeat_fail": "2회 연속 실패 시 flaky 해제, 실제 결함으로 승격",
        },
        "fail_fast_policy": {
            "schema_contract_mismatch": "즉시 FAIL",
            "auth_or_secret_missing": "즉시 FAIL",
            "db_bootstrap_unreachable": "즉시 FAIL",
        },
        "qa_report_flaky_section": {
            "required_fields": [
                "flake_count",
                "suspect_cases(run_id/step/recovery_link)",
                "retry_applied_count",
                "escalated_real_fail_count",
            ]
        },
    }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "window_runs": limit,
        "summary": {
            "total_runs": total,
            "failed_runs": len(failed_runs),
            "success_runs": len(success_runs),
            "failure_rate": round((len(failed_runs) / total) * 100.0, 2),
        },
        "workflow_event_breakdown": {
            key: dict(counter)
            for key, counter in sorted(wf_event_counter.items())
        },
        "runs": [
            {
                "run_id": r.run_id,
                "workflow": r.workflow,
                "event": r.event,
                "conclusion": r.conclusion,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "url": r.url,
                "head_sha": r.head_sha,
            }
            for r in runs
        ],
        "failures": failures_payload,
        "failed_step_patterns": failed_step_patterns,
        "flaky_suspects": flaky_suspects,
        "rules": rules,
    }
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Analyze recent workflow runs and produce flaky-detection report")
    p.add_argument("--repo", default="iAmSomething/2026-", help="owner/repo")
    p.add_argument("--limit", type=int, default=20, help="number of recent runs to analyze")
    p.add_argument("--recover-minutes", type=int, default=120, help="recovery window for flaky suspicion")
    p.add_argument("--output", default="data/qa_flaky_detection_report.json", help="output json path")
    args = p.parse_args()

    report = analyze(repo=args.repo, limit=args.limit, recover_minutes=args.recover_minutes)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        f"summary total={summary['total_runs']} success={summary['success_runs']} "
        f"failed={summary['failed_runs']} failure_rate={summary['failure_rate']}%"
    )
    print(f"flaky_suspects={len(report['flaky_suspects'])}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

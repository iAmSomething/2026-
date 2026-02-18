#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(report: dict) -> str:
    summary = report.get("summary", {})
    api = report.get("api_contract", {})
    staging = report.get("staging_smoke", {})

    lines = []
    lines.append("# Week3 QA Integrated Summary")
    lines.append("")
    lines.append(f"- Overall: **{summary.get('overall_status', 'UNKNOWN')}**")
    lines.append(f"- API Contract: total={api.get('total', 0)}, pass={api.get('pass', 0)}, fail={api.get('fail', 0)}")
    lines.append(
        f"- Staging Smoke (manual): {staging.get('manual', {}).get('conclusion', 'unknown')}"
        f" ({staging.get('manual', {}).get('url', '-')})"
    )
    lines.append(
        f"- Staging Smoke (auto/push): {staging.get('auto', {}).get('conclusion', 'unknown')}"
        f" ({staging.get('auto', {}).get('url', '-')})"
    )
    lines.append("")
    lines.append("## Gate Decision")
    lines.append(f"- {summary.get('gate_decision', 'NOT_SET')}")
    lines.append("")
    lines.append("## Notes")
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Generate markdown summary from week3 QA integrated JSON report")
    p.add_argument("--input", required=True, help="input JSON report path")
    p.add_argument("--output", required=True, help="output markdown path")
    args = p.parse_args()

    src = Path(args.input)
    out = Path(args.output)
    report = json.loads(src.read_text(encoding="utf-8"))
    out.write_text(render(report), encoding="utf-8")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

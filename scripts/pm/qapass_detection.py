#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

QA_PASS_LINE_RE = re.compile(r"(?m)^\[QA PASS\](?:\s|$)")


def has_qa_pass_comment(comment_bodies: list[str]) -> bool:
    for body in comment_bodies:
        if QA_PASS_LINE_RE.search(body):
            return True
    return False


def _extract_bodies_from_issue_json(payload: dict[str, Any]) -> list[str]:
    comments = payload.get("comments", [])
    out: list[str] = []
    for item in comments:
        body = item.get("body")
        if isinstance(body, str):
            out.append(body)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict QA PASS comment detector")
    parser.add_argument(
        "--mode",
        default="issue-json",
        choices=("issue-json", "comments-array"),
        help="input payload mode",
    )
    args = parser.parse_args()

    raw = sys.stdin.read()
    if not raw.strip():
        return 1

    payload = json.loads(raw)
    if args.mode == "comments-array":
        if not isinstance(payload, list):
            raise ValueError("comments-array mode expects JSON string array")
        bodies = [x for x in payload if isinstance(x, str)]
    else:
        if not isinstance(payload, dict):
            raise ValueError("issue-json mode expects object with comments[].body")
        bodies = _extract_bodies_from_issue_json(payload)

    return 0 if has_qa_pass_comment(bodies) else 1


if __name__ == "__main__":
    raise SystemExit(main())

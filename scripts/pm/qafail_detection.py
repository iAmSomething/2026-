#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

# Match only explicit FAIL verdict lines.
FAIL_LINE_PATTERNS = (
    re.compile(r"(?mi)^\s*\[QA FAIL\]\s*$"),
    re.compile(r"(?mi)^\s*(?:-\s*)?status:\s*fail\s*$"),
    re.compile(r"(?mi)^\s*(?:-\s*)?verdict:\s*fail\s*$"),
    re.compile(r"(?m)^\s*(?:-\s*)?판정\s*:\s*FAIL\s*$"),
    re.compile(r"(?m)^\s*(?:-\s*)?결론\s*:\s*Done 처리 불가\s*$"),
)


def has_qa_fail_report_text(text: str) -> bool:
    for pattern in FAIL_LINE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict QA FAIL report detector")
    parser.add_argument("--file", required=True, help="QA report markdown file path")
    args = parser.parse_args()

    text = Path(args.file).read_text(encoding="utf-8")
    return 0 if has_qa_fail_report_text(text) else 1


if __name__ == "__main__":
    raise SystemExit(main())

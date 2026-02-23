#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from app.services.ingest_input_normalization import normalize_ingest_payload


def normalize_payload(payload: dict) -> dict:
    return normalize_ingest_payload(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize ingest payload candidate fields for scheduled ingest")
    parser.add_argument("--input", required=True, help="input payload json path")
    parser.add_argument("--output", required=True, help="output payload json path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    normalized = normalize_payload(payload)
    Path(args.output).write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

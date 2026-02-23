#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_SOURCES = {"name_rule", "article_context", "manual"}
TRUE_TOKENS = {"1", "true", "yes", "y", "on"}
FALSE_TOKENS = {"0", "false", "no", "n", "off"}


def _normalize_party_inferred(value: Any, party_name: str | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in TRUE_TOKENS:
            return True
        if token in FALSE_TOKENS or token == "":
            return False
        return True
    if isinstance(party_name, str) and party_name.strip():
        return True
    return False


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    records = payload.get("records") or []
    for record in records:
        for candidate in record.get("candidates") or []:
            party_name = candidate.get("party_name")
            original = candidate.get("party_inferred")
            normalized_bool = _normalize_party_inferred(original, party_name)
            candidate["party_inferred"] = normalized_bool

            if (
                normalized_bool
                and (not isinstance(party_name, str) or not party_name.strip())
                and isinstance(original, str)
                and original.strip().lower() not in TRUE_TOKENS | FALSE_TOKENS
            ):
                candidate["party_name"] = original.strip()

            source = candidate.get("party_inference_source")
            if source not in ALLOWED_SOURCES:
                candidate["party_inference_source"] = "manual" if normalized_bool else None
    return payload


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

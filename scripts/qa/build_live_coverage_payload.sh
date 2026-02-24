#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="python3"
V2_SCRIPT="scripts/generate_collector_live_coverage_v2_pack.py"
V1_SCRIPT="scripts/generate_collector_live_coverage_v1_pack.py"
V2_PAYLOAD="data/collector_live_coverage_v2_payload.json"
V1_PAYLOAD="data/collector_live_coverage_v1_payload.json"
CANONICAL_PAYLOAD="data/collector_live_coverage_v1_payload.json"
ROUTE_REPORT="data/ingest_schedule_payload_route_report.json"
ROUTE_MODE="unknown"

usage() {
  cat <<USAGE
Usage: $0 [options]

Options:
  --python <path>            Python interpreter (default: python3)
  --v2-script <path>         V2 generator script path
  --v1-script <path>         V1 generator script path
  --v2-payload <path>        V2 payload output path
  --v1-payload <path>        V1 payload output path
  --canonical-payload <path> Canonical downstream payload path
  --route-report <path>      Route metadata report path
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --v2-script)
      V2_SCRIPT="${2:-}"
      shift 2
      ;;
    --v1-script)
      V1_SCRIPT="${2:-}"
      shift 2
      ;;
    --v2-payload)
      V2_PAYLOAD="${2:-}"
      shift 2
      ;;
    --v1-payload)
      V1_PAYLOAD="${2:-}"
      shift 2
      ;;
    --canonical-payload)
      CANONICAL_PAYLOAD="${2:-}"
      shift 2
      ;;
    --route-report)
      ROUTE_REPORT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

mkdir -p "$(dirname "$CANONICAL_PAYLOAD")"

run_generator() {
  local script_path="$1"
  shift
  local py_path="${PYTHONPATH:-}"
  if [[ -n "$py_path" ]]; then
    PYTHONPATH=".:$py_path" "$PYTHON_BIN" "$script_path" "$@"
  else
    PYTHONPATH="." "$PYTHON_BIN" "$script_path" "$@"
  fi
}

if [[ -f "$V2_SCRIPT" ]]; then
  echo "[build-live-coverage] generator=v2 script=$V2_SCRIPT"
  run_generator "$V2_SCRIPT"
  test -s "$V2_PAYLOAD"
  cp "$V2_PAYLOAD" "$CANONICAL_PAYLOAD"
  ROUTE_MODE="collector_live_v2"
elif [[ -f "$V1_SCRIPT" ]]; then
  echo "[build-live-coverage] generator=v1 script=$V1_SCRIPT"
  run_generator "$V1_SCRIPT"
  if [[ "$V1_PAYLOAD" != "$CANONICAL_PAYLOAD" ]]; then
    test -s "$V1_PAYLOAD"
    cp "$V1_PAYLOAD" "$CANONICAL_PAYLOAD"
  fi
  ROUTE_MODE="collector_live_v1"
else
  echo "[build-live-coverage] no generator found. checked: $V2_SCRIPT, $V1_SCRIPT" >&2
  exit 1
fi

test -s "$CANONICAL_PAYLOAD"

# Ingest API contract expects strict bool/literal candidate fields.
run_generator "scripts/qa/normalize_ingest_payload_for_schedule.py" \
  --input "$CANONICAL_PAYLOAD" \
  --output "$CANONICAL_PAYLOAD"

ROUTE_MODE="$ROUTE_MODE" CANONICAL_PAYLOAD="$CANONICAL_PAYLOAD" ROUTE_REPORT="$ROUTE_REPORT" "$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

canonical = Path(os.environ["CANONICAL_PAYLOAD"])
route_report = Path(os.environ["ROUTE_REPORT"])
route_report.parent.mkdir(parents=True, exist_ok=True)
payload = json.loads(canonical.read_text(encoding="utf-8"))
records = payload.get("records") or []
report = {
    "source_mode": os.environ.get("ROUTE_MODE", "unknown"),
    "canonical_payload": str(canonical),
    "record_count": len(records),
    "run_type": payload.get("run_type"),
    "extractor_version": payload.get("extractor_version"),
}
route_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[build-live-coverage] route_report={route_report}")
print(f"[build-live-coverage] route_report_json={json.dumps(report, ensure_ascii=False)}")
PY

echo "[build-live-coverage] canonical_payload=$CANONICAL_PAYLOAD"

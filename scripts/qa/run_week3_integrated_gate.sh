#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

MANUAL_RUN_URL=""
AUTO_RUN_URL=""
OUT_JSON="data/qa_week3_integrated_report.json"
OUT_MD="data/qa_week3_integrated_summary.md"
API_REPORT="data/qa_api_contract_report.json"

usage() {
  cat <<USAGE
Usage: $0 --manual-run-url <url> --auto-run-url <url> [--out-json path] [--out-md path]

Runs API contract suite locally and composes integrated Week3 QA gate report
with staging smoke manual+auto run results.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manual-run-url)
      MANUAL_RUN_URL="${2:-}"
      shift 2
      ;;
    --auto-run-url)
      AUTO_RUN_URL="${2:-}"
      shift 2
      ;;
    --out-json)
      OUT_JSON="${2:-}"
      shift 2
      ;;
    --out-md)
      OUT_MD="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$MANUAL_RUN_URL" || -z "$AUTO_RUN_URL" ]]; then
  echo "[FAIL] --manual-run-url and --auto-run-url are required"
  exit 1
fi

mkdir -p "$(dirname "$OUT_JSON")"
mkdir -p "$(dirname "$OUT_MD")"

extract_run_id() {
  local url="$1"
  echo "$url" | sed -E 's#^.*/runs/([0-9]+).*$#\1#'
}

MANUAL_RUN_ID="$(extract_run_id "$MANUAL_RUN_URL")"
AUTO_RUN_ID="$(extract_run_id "$AUTO_RUN_URL")"

if [[ ! "$MANUAL_RUN_ID" =~ ^[0-9]+$ || ! "$AUTO_RUN_ID" =~ ^[0-9]+$ ]]; then
  echo "[FAIL] invalid run url(s)"
  exit 1
fi

echo "[STEP] API contract suite"
scripts/qa/run_api_contract_suite.sh --report "$API_REPORT"

echo "[STEP] Fetch staging smoke run metadata"
gh run view "$MANUAL_RUN_ID" --repo iAmSomething/2026- --json databaseId,conclusion,event,url,headSha,createdAt,updatedAt,name,workflowName,status > /tmp/qa_week3_manual_run.json
gh run view "$AUTO_RUN_ID" --repo iAmSomething/2026- --json databaseId,conclusion,event,url,headSha,createdAt,updatedAt,name,workflowName,status > /tmp/qa_week3_auto_run.json

python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path

api = json.loads(Path("$API_REPORT").read_text(encoding="utf-8"))
manual = json.loads(Path('/tmp/qa_week3_manual_run.json').read_text(encoding='utf-8'))
auto = json.loads(Path('/tmp/qa_week3_auto_run.json').read_text(encoding='utf-8'))

api_fail = int(api.get('summary', {}).get('fail', 0))
manual_ok = manual.get('conclusion') == 'success'
auto_ok = auto.get('conclusion') == 'success'

overall_ok = api_fail == 0 and manual_ok and auto_ok

report = {
    'suite': 'qa_week3_integrated_gate',
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'api_contract': api.get('summary', {}),
    'staging_smoke': {
        'manual': manual,
        'auto': auto,
    },
    'summary': {
        'overall_status': 'PASS' if overall_ok else 'FAIL',
        'gate_decision': 'Week3 integrated QA gate passed' if overall_ok else 'Week3 integrated QA gate failed',
    },
    'notes': [
        'API contract suite + staging smoke manual/auto run were combined as a single integrated gate.',
        'Staging smoke provides UI/API/ingest E2E coverage.',
    ],
}

Path("$OUT_JSON").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print('written:', "$OUT_JSON")
print('overall:', report['summary']['overall_status'])
PY

scripts/qa/generate_week3_qa_summary.py --input "$OUT_JSON" --output "$OUT_MD"

echo "[PASS] integrated gate composed"

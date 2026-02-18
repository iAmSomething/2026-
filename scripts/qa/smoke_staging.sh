#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8100}"
WEB_BASE="${WEB_BASE:-http://127.0.0.1:3300}"
SAMPLE_INPUT="${SAMPLE_INPUT:-data/sample_ingest.json}"
SKIP_INGEST=0
LOG_FILE=""

usage() {
  cat <<USAGE
Usage: $0 [--api-base URL] [--web-base URL] [--sample-input PATH] [--skip-ingest] [--log-file PATH]

Required env (unless --skip-ingest):
  INTERNAL_JOB_TOKEN
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base)
      API_BASE="${2:-}"
      shift 2
      ;;
    --web-base)
      WEB_BASE="${2:-}"
      shift 2
      ;;
    --sample-input)
      SAMPLE_INPUT="${2:-}"
      shift 2
      ;;
    --skip-ingest)
      SKIP_INGEST=1
      shift
      ;;
    --log-file)
      LOG_FILE="${2:-}"
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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f "$SAMPLE_INPUT" ]]; then
  echo "[FAIL] sample input not found: $SAMPLE_INPUT"
  exit 1
fi

if [[ "$SKIP_INGEST" -eq 0 && -z "${INTERNAL_JOB_TOKEN:-}" ]]; then
  echo "[FAIL] INTERNAL_JOB_TOKEN is required unless --skip-ingest is set"
  exit 1
fi

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[FAIL] python not found: $PYTHON_BIN"
  exit 1
fi

echo "[INFO] API_BASE=$API_BASE"
echo "[INFO] WEB_BASE=$WEB_BASE"

echo "[CHECK] API health"
curl -fsS "$API_BASE/health" >/dev/null

if [[ "$SKIP_INGEST" -eq 0 ]]; then
  echo "[CHECK] Trigger ingest job"
  curl -fsS \
    -X POST "$API_BASE/api/v1/jobs/run-ingest" \
    -H "Authorization: Bearer $INTERNAL_JOB_TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary "@$SAMPLE_INPUT" >/tmp/staging_ingest_result.json
fi

CANDIDATE_ID="$($PYTHON_BIN - <<PY
import json
from pathlib import Path
obj=json.loads(Path("$SAMPLE_INPUT").read_text(encoding="utf-8"))
candidate_id="cand-jwo"
records=obj.get("records",[])
for record in records:
    candidates = record.get("candidates", [])
    if not candidates:
        continue
    resolved = candidates[0].get("candidate_id")
    if resolved:
        candidate_id = resolved
        break
print(candidate_id)
PY
)"

echo "[CHECK] dashboard summary contract"
"$PYTHON_BIN" - <<PY
import json, urllib.request
base="$API_BASE"
obj=json.loads(urllib.request.urlopen(base+"/api/v1/dashboard/summary", timeout=10).read().decode())
assert "party_support" in obj
assert "presidential_approval" in obj
print("summary_ok", len(obj.get("party_support", [])), len(obj.get("presidential_approval", [])))
PY

echo "[CHECK] regions search contract"
"$PYTHON_BIN" - <<PY
import json, urllib.parse, urllib.request
base="$API_BASE"
url=base+"/api/v1/regions/search?"+urllib.parse.urlencode({"q":"서울"})
obj=json.loads(urllib.request.urlopen(url, timeout=10).read().decode())
assert isinstance(obj, list)
if obj:
    row=obj[0]
    for key in ("region_code","sido_name","sigungu_name","admin_level"):
        assert key in row
print("regions_ok", len(obj))
PY

echo "[CHECK] candidate contract"
"$PYTHON_BIN" - <<PY
import json, urllib.request
base="$API_BASE"
candidate_id="$CANDIDATE_ID"
obj=json.loads(urllib.request.urlopen(base+f"/api/v1/candidates/{candidate_id}", timeout=10).read().decode())
for key in ("candidate_id","name_ko","party_name"):
    assert key in obj
print("candidate_ok", obj["candidate_id"])
PY

echo "[CHECK] web home responds"
HTTP_CODE="$(curl -sS -o /tmp/staging_web_home.html -w "%{http_code}" "$WEB_BASE/")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "[FAIL] web home status: $HTTP_CODE"
  exit 1
fi
"$PYTHON_BIN" - <<PY
from pathlib import Path
html = Path("/tmp/staging_web_home.html").read_text(encoding="utf-8", errors="ignore")
assert "최신 정당 여론조사" in html or "Election 2026" in html
print("web_ok")
PY

if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
  echo "[CHECK] secret masking in logs"
  if rg -n "sb_secret_|SUPABASE_SERVICE_ROLE_KEY=|INTERNAL_JOB_TOKEN=" "$LOG_FILE" >/dev/null 2>&1; then
    echo "[FAIL] sensitive token pattern detected in log file: $LOG_FILE"
    exit 1
  fi
fi

echo "[PASS] staging smoke checks completed"

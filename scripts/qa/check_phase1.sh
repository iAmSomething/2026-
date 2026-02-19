#!/usr/bin/env bash
set -euo pipefail

WITH_DB=0
WITH_API=0
STRICT=0
API_BASE="http://127.0.0.1:8000"

usage() {
  cat <<USAGE
Usage: $0 [--with-db] [--with-api] [--api-base URL] [--strict]

Default checks:
  - pytest pass
  - sample ingest artifact existence/shape
  - collector precision artifact threshold (if present)

Optional checks:
  --with-db   run schema + ingest x2 + DB idempotency checks
  --with-api  verify 3 API contracts (summary/regions/candidate)

Flags:
  --strict    treat warnings as failures
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-db)
      WITH_DB=1
      shift
      ;;
    --with-api)
      WITH_API=1
      shift
      ;;
    --api-base)
      API_BASE="${2:-}"
      shift 2
      ;;
    --strict)
      STRICT=1
      shift
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

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[FAIL] .venv python not found: $PYTHON_BIN"
  exit 1
fi

PASS=0
FAIL=0
WARN=0
TOTAL=0

pass() { echo "[PASS] $1"; PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); }
fail() { echo "[FAIL] $1"; FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); }
warn() { echo "[WARN] $1"; WARN=$((WARN + 1)); TOTAL=$((TOTAL + 1)); }

run_check() {
  local name="$1"
  shift
  if "$@"; then
    pass "$name"
  else
    fail "$name"
  fi
}

echo "== Phase1 QA =="
echo "root: $ROOT_DIR"
echo "python: $($PYTHON_BIN --version 2>/dev/null || true)"
echo "with_db: $WITH_DB, with_api: $WITH_API, api_base: $API_BASE"

# A) Unit/integration tests
run_check "pytest passes" "$PYTHON_BIN" -m pytest -q

# B) Required artifacts
SAMPLE_FILE=""
if [[ -f data/sample_ingest_collector_5.json ]]; then
  SAMPLE_FILE="data/sample_ingest_collector_5.json"
elif [[ -f data/sample_ingest.json ]]; then
  SAMPLE_FILE="data/sample_ingest.json"
fi

if [[ -z "$SAMPLE_FILE" ]]; then
  fail "sample ingest json exists (data/sample_ingest_collector_5.json or data/sample_ingest.json)"
else
  run_check "sample ingest schema has records" "$PYTHON_BIN" - <<PY
import json
from pathlib import Path
p=Path("$SAMPLE_FILE")
obj=json.loads(p.read_text(encoding="utf-8"))
records=obj.get("records",[])
assert isinstance(records,list)
assert len(records)>=1
print("records",len(records))
PY
fi

if [[ -f data/collector_precision_report.json ]]; then
  run_check "collector precision >= 0.90 and sample_count >= 30" "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path("data/collector_precision_report.json").read_text(encoding="utf-8"))
precision=float(obj.get("precision",0))
sample_count=int(obj.get("sample_count",0))
assert precision>=0.90, precision
assert sample_count>=30, sample_count
print("precision",precision,"sample_count",sample_count)
PY
else
  warn "collector precision report missing: data/collector_precision_report.json"
fi

# C) Optional DB checks
if [[ "$WITH_DB" -eq 1 ]]; then
  if [[ -z "${DATABASE_URL:-}" ]]; then
    fail "DATABASE_URL is required for --with-db"
  else
    run_check "apply schema" "$PYTHON_BIN" scripts/init_db.py

    run_check "manual ingest first run" "$PYTHON_BIN" -m app.jobs.manual_ingest --input "$SAMPLE_FILE"
    run_check "manual ingest second run" "$PYTHON_BIN" -m app.jobs.manual_ingest --input "$SAMPLE_FILE"

    run_check "db idempotency/constraints sanity" "$PYTHON_BIN" - <<'PY'
import os
import psycopg
url=os.environ["DATABASE_URL"]
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("select count(*), count(distinct url) from articles")
        total, uniq = cur.fetchone(); assert total==uniq
        cur.execute("select count(*), count(distinct observation_key) from poll_observations")
        total, uniq = cur.fetchone(); assert total==uniq
        cur.execute("select count(*) from ingestion_runs")
        runs = cur.fetchone()[0]; assert runs >= 2
        cur.execute("""
            select value_min, value_max, value_mid, is_missing
            from poll_options where value_raw='53~55%' limit 1
        """)
        row = cur.fetchone()
        if row is not None:
            assert float(row[0])==53.0
            assert float(row[1])==55.0
            assert float(row[2])==54.0
            assert row[3] is False
print("db checks ok")
PY
  fi
fi

# D) Optional API checks
SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "$WITH_API" -eq 1 ]]; then
  HEALTH_URL="$API_BASE/health"
  if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    HOST_PORT="${API_BASE#http://}"
    HOST="${HOST_PORT%%:*}"
    PORT="${HOST_PORT##*:}"
    if [[ "$HOST" == "$PORT" ]]; then
      HOST="127.0.0.1"
      PORT="8000"
    fi
    "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" >/tmp/phase1_api.log 2>&1 &
    SERVER_PID=$!
    for _ in $(seq 1 25); do
      if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then break; fi
      sleep 0.4
    done
  fi

  run_check "api health" curl -fsS "$HEALTH_URL"

  run_check "api summary contract" "$PYTHON_BIN" - <<PY
import json, urllib.request
base="$API_BASE"
obj=json.loads(urllib.request.urlopen(base+"/api/v1/dashboard/summary").read().decode())
assert "party_support" in obj
assert "presidential_approval" in obj
if obj["party_support"]:
    for k in ["option_name","value_mid","pollster","survey_end_date","verified"]:
        assert k in obj["party_support"][0]
print("summary ok")
PY

  run_check "api regions/search contract" "$PYTHON_BIN" - <<PY
import json, urllib.request, urllib.parse
base="$API_BASE"
url=base+"/api/v1/regions/search?"+urllib.parse.urlencode({"q":"서울"})
obj=json.loads(urllib.request.urlopen(url).read().decode())
assert isinstance(obj,list)
if obj:
    for k in ["region_code","sido_name","sigungu_name","admin_level"]:
        assert k in obj[0]
print("regions ok")
PY

  run_check "api candidate contract" "$PYTHON_BIN" - <<PY
import json, urllib.request
base="$API_BASE"
candidate_id="cand-jwo"
obj=json.loads(urllib.request.urlopen(base+f"/api/v1/candidates/{candidate_id}").read().decode())
for k in [
    "candidate_id","name_ko","party_name",
    "party_inferred","party_inference_source","party_inference_confidence","needs_manual_review"
]:
    assert k in obj
assert isinstance(obj["party_inferred"], bool)
assert isinstance(obj["needs_manual_review"], bool)
assert obj["party_inference_source"] is None or isinstance(obj["party_inference_source"], str)
assert obj["party_inference_confidence"] is None or isinstance(obj["party_inference_confidence"], (int, float))
print("candidate ok")
PY
fi

# E) Issue status overview (non-blocking)
if command -v gh >/dev/null 2>&1; then
  CORE_CLOSED=$(gh issue list --repo iAmSomething/2026- --state closed --limit 50 --json number --jq '[.[].number] | map(select(.==2 or .==3 or .==6 or .==8 or .==9)) | length')
  if [[ "$CORE_CLOSED" -ge 5 ]]; then
    pass "core execution issues closed (#2,#3,#6,#8,#9)"
  else
    warn "core execution issues not fully closed"
  fi

  if gh issue view 7 --repo iAmSomething/2026- --json state --jq '.state' | grep -q "OPEN"; then
    warn "security gate (#7 rotate) still open"
  else
    pass "security gate (#7) closed"
  fi
fi

if [[ "$STRICT" -eq 1 && "$WARN" -gt 0 ]]; then
  FAIL=$((FAIL + WARN))
  WARN=0
fi

echo
echo "== Summary =="
echo "checks: $TOTAL, pass: $PASS, fail: $FAIL, warn: $WARN"

if [[ "$FAIL" -gt 0 ]]; then
  echo "Phase1 QA: FAIL"
  exit 1
fi

echo "Phase1 QA: PASS"

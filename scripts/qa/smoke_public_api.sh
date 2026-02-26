#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-https://2026-api-production.up.railway.app}"
WEB_ORIGIN="${WEB_ORIGIN:-https://2026-deploy.vercel.app}"
OUT_DIR="${OUT_DIR:-/tmp/public_api_smoke}"
STRICT_CONTRACT="${STRICT_CONTRACT:-0}"

usage() {
  cat <<USAGE
Usage: $0 [--api-base URL] [--web-origin URL] [--out-dir PATH]
          [--strict-contract]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base)
      API_BASE="${2:-}"
      shift 2
      ;;
    --web-origin)
      WEB_ORIGIN="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --strict-contract)
      STRICT_CONTRACT=1
      shift 1
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

mkdir -p "$OUT_DIR"

request() {
  local label="$1"
  local path="$2"
  local body="$OUT_DIR/${label}.json"
  local status
  status="$(curl -sS -o "$body" -w "%{http_code}" "${API_BASE}${path}" || true)"
  echo "${label} ${status}"
}

echo "[INFO] API_BASE=${API_BASE}"
echo "[INFO] WEB_ORIGIN=${WEB_ORIGIN}"
echo "[INFO] STRICT_CONTRACT=${STRICT_CONTRACT}"

health_status="$(request "health" "/health" | awk '{print $2}')"
summary_status="$(request "summary" "/api/v1/dashboard/summary" | awk '{print $2}')"
regions_status="$(request "regions" "/api/v1/regions/search?q=%EC%84%9C%EC%9A%B8" | awk '{print $2}')"
candidate_status="$(request "candidate" "/api/v1/candidates/cand-jwo" | awk '{print $2}')"

map_latest_status=""
sejong_status=""
if [[ "$STRICT_CONTRACT" == "1" ]]; then
  map_latest_status="$(request "map_latest" "/api/v1/dashboard/map-latest?limit=200" | awk '{print $2}')"
  sejong_status="$(request "sejong_elections" "/api/v1/regions/29-000/elections" | awk '{print $2}')"
fi

curl -sS -D "$OUT_DIR/cors_headers.txt" -o "$OUT_DIR/cors_body.txt" \
  -X OPTIONS "${API_BASE}/api/v1/dashboard/summary" \
  -H "Origin: ${WEB_ORIGIN}" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: content-type" || true

cors_status="$(awk 'NR==1 {print $2}' "$OUT_DIR/cors_headers.txt")"
cors_allow_origin="$(awk -F': ' 'tolower($1)=="access-control-allow-origin" {print $2}' "$OUT_DIR/cors_headers.txt" | tr -d '\r')"

echo "[RESULT] health=${health_status} summary=${summary_status} regions=${regions_status} candidate=${candidate_status} cors=${cors_status}"
echo "[RESULT] cors_allow_origin=${cors_allow_origin:-<empty>}"
if [[ "$STRICT_CONTRACT" == "1" ]]; then
  echo "[RESULT] strict map_latest=${map_latest_status} sejong_elections=${sejong_status}"
fi

failed=0
[[ "$health_status" == "200" ]] || failed=1
[[ "$summary_status" == "200" ]] || failed=1
[[ "$regions_status" == "200" ]] || failed=1
[[ "$candidate_status" == "200" || "$candidate_status" == "404" ]] || failed=1
[[ "$cors_status" == "200" || "$cors_status" == "204" ]] || failed=1
[[ "${cors_allow_origin:-}" == "$WEB_ORIGIN" ]] || failed=1

if [[ "$STRICT_CONTRACT" == "1" ]]; then
  [[ "$map_latest_status" == "200" ]] || failed=1
  [[ "$sejong_status" == "200" ]] || failed=1

  if ! command -v jq >/dev/null 2>&1; then
    echo "[FAIL] strict-contract requires jq"
    failed=1
  else
    map_noise_count="$(
      jq '[.items[]?.option_name | select(.=="재정자립도" or .=="지지" or .=="국정안정론" or .=="국정견제론")] | length' \
        "$OUT_DIR/map_latest.json" 2>/dev/null || echo "-1"
    )"
    sejong_bad_title_count="$(
      jq '[.[]? | select(.region_code=="29-000" and ((.title | tostring) | contains("세종") | not))] | length' \
        "$OUT_DIR/sejong_elections.json" 2>/dev/null || echo "-1"
    )"

    echo "[RESULT] strict map_noise_count=${map_noise_count} sejong_bad_title_count=${sejong_bad_title_count}"

    [[ "$map_noise_count" =~ ^[0-9]+$ ]] || failed=1
    [[ "$sejong_bad_title_count" =~ ^[0-9]+$ ]] || failed=1

    if [[ "$map_noise_count" =~ ^[0-9]+$ ]] && [[ "$map_noise_count" -gt 0 ]]; then
      failed=1
    fi
    if [[ "$sejong_bad_title_count" =~ ^[0-9]+$ ]] && [[ "$sejong_bad_title_count" -gt 0 ]]; then
      failed=1
    fi
  fi
fi

if [[ "$failed" -eq 1 ]]; then
  echo "[FAIL] public API smoke check failed"
  exit 1
fi

echo "[PASS] public API smoke check passed"

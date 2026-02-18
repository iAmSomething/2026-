#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  REQUIRED_SECRETS=("$@")
else
  REQUIRED_SECRETS=(
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    DATA_GO_KR_KEY
    DATABASE_URL
    INTERNAL_JOB_TOKEN
  )
fi

missing=()
invalid=()
warnings=()

is_present() {
  local name="$1"
  local value="${!name:-}"
  [[ -n "${value// }" ]]
}

for name in "${REQUIRED_SECRETS[@]}"; do
  if ! is_present "$name"; then
    missing+=("$name")
    continue
  fi
  value="${!name}"
  echo "[OK] $name is set (len=${#value})"
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "[FAIL] Missing required secrets: ${missing[*]}"
  echo "Guide:"
  echo "1) GitHub Repo > Settings > Secrets and variables > Actions > Repository secrets"
  echo "2) Add missing names exactly as listed above"
  echo "3) Re-run workflow after saving"
  exit 1
fi

if [[ ! "${SUPABASE_URL:-}" =~ ^https://[a-z0-9-]+\.supabase\.co/?$ ]]; then
  invalid+=("SUPABASE_URL (expected: https://<project-ref>.supabase.co)")
fi

if [[ ! "${DATABASE_URL:-}" =~ ^postgres(ql)?:// ]]; then
  invalid+=("DATABASE_URL (expected PostgreSQL URI)")
fi

if [[ ${#INTERNAL_JOB_TOKEN} -lt 16 ]]; then
  invalid+=("INTERNAL_JOB_TOKEN (length should be >= 16)")
fi

if [[ ! "${SUPABASE_SERVICE_ROLE_KEY:-}" =~ ^(sb_secret_|eyJ) ]]; then
  warnings+=("SUPABASE_SERVICE_ROLE_KEY prefix is unusual; verify key source")
fi

if [[ ${#DATA_GO_KR_KEY} -lt 8 ]]; then
  warnings+=("DATA_GO_KR_KEY looks too short; verify Data.go.kr key")
fi

if [[ ${#invalid[@]} -gt 0 ]]; then
  echo "[FAIL] Invalid secret format:"
  for line in "${invalid[@]}"; do
    echo " - $line"
  done
  exit 1
fi

if [[ ${#warnings[@]} -gt 0 ]]; then
  echo "[WARN] Secret validation warnings:"
  for line in "${warnings[@]}"; do
    echo " - $line"
  done
fi

echo "[PASS] Required secrets preflight passed"

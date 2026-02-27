#!/usr/bin/env bash
set -eo pipefail

MODE="dry-run"
STALE_HOURS=24
BASE_DIR="${WORKTREE_HYGIENE_BASE_DIR:-$HOME}"
REPORT_PATH="${WORKTREE_HYGIENE_REPORT_PATH:-data/worktree_hygiene_report.txt}"
GIT_BIN="${WORKTREE_HYGIENE_GIT:-git}"
NOW_EPOCH="${WORKTREE_HYGIENE_NOW_EPOCH:-$(date +%s)}"
WORKTREE_LIST_FILE="${WORKTREE_HYGIENE_WORKTREE_LIST_FILE:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/pm/worktree_hygiene.sh [--mode dry-run|apply] [--hours N] [--base-dir PATH] [--report PATH]

Options:
  --mode       dry-run (default) or apply
  --hours      stale threshold in hours (default: 24)
  --base-dir   directory to scan (default: $HOME)
  --report     output report path (default: data/worktree_hygiene_report.txt)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --hours)
      STALE_HOURS="${2:-}"
      shift 2
      ;;
    --base-dir)
      BASE_DIR="${2:-}"
      shift 2
      ;;
    --report)
      REPORT_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "${MODE}" != "dry-run" && "${MODE}" != "apply" ]]; then
  echo "Invalid --mode: ${MODE}. Use dry-run or apply."
  exit 1
fi

if ! [[ "${STALE_HOURS}" =~ ^[0-9]+$ ]]; then
  echo "Invalid --hours: ${STALE_HOURS}. Use non-negative integer."
  exit 1
fi

if [[ ! -d "${BASE_DIR}" ]]; then
  echo "Base directory not found: ${BASE_DIR}"
  exit 1
fi

_canon() {
  local path="$1"
  (cd "$path" >/dev/null 2>&1 && pwd -P) || return 1
}

_mtime_epoch() {
  local path="$1"
  if stat -f %m "$path" >/dev/null 2>&1; then
    stat -f %m "$path"
  else
    stat -c %Y "$path"
  fi
}

if ! BASE_DIR="$(_canon "${BASE_DIR}")"; then
  echo "Failed to resolve base directory: ${BASE_DIR}"
  exit 1
fi

_is_managed_name() {
  local name="$1"
  [[ "$name" == election2026_codex_issue* ]] \
    || [[ "$name" == election2026_issue* ]] \
    || [[ "$name" == election2026_runtime* ]] \
    || [[ "$name" == election2026_codex_runtime* ]]
}

_list_contains() {
  local needle="$1"
  shift
  for item in "$@"; do
    if [[ "$item" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

active_worktrees=()
if [[ -n "${WORKTREE_LIST_FILE}" && -f "${WORKTREE_LIST_FILE}" ]]; then
  while IFS= read -r line; do
    [[ "$line" == worktree\ * ]] || continue
    raw_path="${line#worktree }"
    if abs_path="$(_canon "$raw_path")"; then
      if ! _list_contains "${abs_path}" ${active_worktrees[@]+"${active_worktrees[@]}"}; then
        active_worktrees+=("${abs_path}")
      fi
    fi
  done < "${WORKTREE_LIST_FILE}"
else
  while IFS= read -r line; do
    [[ "$line" == worktree\ * ]] || continue
    raw_path="${line#worktree }"
    if abs_path="$(_canon "$raw_path")"; then
      if ! _list_contains "${abs_path}" ${active_worktrees[@]+"${active_worktrees[@]}"}; then
        active_worktrees+=("${abs_path}")
      fi
    fi
  done < <("${GIT_BIN}" -C "${REPO_ROOT}" worktree list --porcelain 2>/dev/null || true)
fi

seen_paths=()
candidate_paths=()
candidate_ages=()
excluded_rows=()
deleted_paths=()
error_rows=()

managed_patterns=(
  "election2026_codex"
  "election2026_codex_issue*"
  "election2026_issue*"
  "election2026_runtime*"
  "election2026_codex_runtime*"
)

for pattern in "${managed_patterns[@]}"; do
  for raw_path in "${BASE_DIR}"/${pattern}; do
    [[ -e "${raw_path}" ]] || continue
    [[ -d "${raw_path}" ]] || continue

    if ! abs_path="$(_canon "${raw_path}")"; then
      continue
    fi
    if _list_contains "${abs_path}" ${seen_paths[@]+"${seen_paths[@]}"}; then
      continue
    fi
    seen_paths+=("${abs_path}")

    base_name="$(basename "${abs_path}")"
    if [[ "${abs_path}" == "${REPO_ROOT}" || "${base_name}" == "election2026_codex" ]]; then
      excluded_rows+=("${abs_path}|protected_root")
      continue
    fi

    if _list_contains "${abs_path}" ${active_worktrees[@]+"${active_worktrees[@]}"}; then
      excluded_rows+=("${abs_path}|active_worktree")
      continue
    fi

    modified_epoch="$(_mtime_epoch "${abs_path}")"
    age_hours=$(( (NOW_EPOCH - modified_epoch) / 3600 ))
    if (( age_hours >= STALE_HOURS )); then
      candidate_paths+=("${abs_path}")
      candidate_ages+=("${age_hours}")
    else
      excluded_rows+=("${abs_path}|fresh(${age_hours}h)")
    fi
  done
done

if [[ "${MODE}" == "apply" ]]; then
  for idx in "${!candidate_paths[@]}"; do
    path="${candidate_paths[$idx]}"
    name="$(basename "${path}")"
    if [[ "${path}" != "${BASE_DIR}"/* ]] || ! _is_managed_name "${name}"; then
      error_rows+=("${path}|guard_rejected")
      continue
    fi
    if rm -rf -- "${path}"; then
      deleted_paths+=("${path}")
    else
      error_rows+=("${path}|delete_failed")
    fi
  done
fi

mkdir -p "$(dirname "${REPORT_PATH}")"
{
  echo "generated_at_epoch=${NOW_EPOCH}"
  echo "mode=${MODE}"
  echo "stale_hours=${STALE_HOURS}"
  echo "base_dir=${BASE_DIR}"
  echo "repo_root=${REPO_ROOT}"
  echo "active_worktree_count=${#active_worktrees[@]}"
  echo "candidate_count=${#candidate_paths[@]}"
  echo "excluded_count=${#excluded_rows[@]}"
  echo "deleted_count=${#deleted_paths[@]}"
  echo "error_count=${#error_rows[@]}"
  echo ""
  echo "[candidates]"
  for idx in "${!candidate_paths[@]}"; do
    echo "${candidate_paths[$idx]}|age_hours=${candidate_ages[$idx]}"
  done
  echo ""
  echo "[excluded]"
  for row in "${excluded_rows[@]}"; do
    echo "${row}"
  done
  echo ""
  echo "[deleted]"
  for row in "${deleted_paths[@]}"; do
    echo "${row}"
  done
  echo ""
  echo "[errors]"
  for row in "${error_rows[@]}"; do
    echo "${row}"
  done
} > "${REPORT_PATH}"

echo "[worktree_hygiene] mode=${MODE} stale_hours=${STALE_HOURS} candidate_count=${#candidate_paths[@]} deleted_count=${#deleted_paths[@]} error_count=${#error_rows[@]}"
echo "[worktree_hygiene] report=${REPORT_PATH}"

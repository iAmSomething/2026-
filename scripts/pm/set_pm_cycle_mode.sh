#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-}"
LANE=""
MAX_CREATE=""
COMMENT_ISSUE=""
CLEAR_COMMENT_ISSUE=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 --repo <owner/repo> --lane <offline|online> [--max-create N] [--comment-issue N] [--clear-comment-issue] [--dry-run]

Policy:
- offline lane: PM_CYCLE_MODE=apply, PM_CYCLE_MAX_CREATE=4 (default)
- online lane: PM_CYCLE_MODE=dry-run, PM_CYCLE_MAX_CREATE=0 (default)

Examples:
  $0 --repo iAmSomething/2026- --lane offline
  $0 --repo iAmSomething/2026- --lane online --comment-issue 19
  $0 --repo iAmSomething/2026- --lane online --clear-comment-issue
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --lane)
      LANE="${2:-}"
      shift 2
      ;;
    --max-create)
      MAX_CREATE="${2:-}"
      shift 2
      ;;
    --comment-issue)
      COMMENT_ISSUE="${2:-}"
      shift 2
      ;;
    --clear-comment-issue)
      CLEAR_COMMENT_ISSUE=1
      shift 1
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ -z "$REPO" ]]; then
  echo "Missing required --repo <owner/repo>"
  exit 1
fi
if [[ "$LANE" != "offline" && "$LANE" != "online" ]]; then
  echo "Missing or invalid --lane <offline|online>"
  exit 1
fi
if [[ -n "$MAX_CREATE" ]] && ! [[ "$MAX_CREATE" =~ ^[0-9]+$ ]]; then
  echo "Invalid --max-create: $MAX_CREATE"
  exit 1
fi
if [[ -n "$COMMENT_ISSUE" ]] && ! [[ "$COMMENT_ISSUE" =~ ^[0-9]+$ ]]; then
  echo "Invalid --comment-issue: $COMMENT_ISSUE"
  exit 1
fi
if [[ -n "$COMMENT_ISSUE" && "$CLEAR_COMMENT_ISSUE" -eq 1 ]]; then
  echo "Use either --comment-issue or --clear-comment-issue, not both."
  exit 1
fi

for cmd in gh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd is required"
    exit 1
  fi
done

if [[ "$LANE" == "offline" ]]; then
  MODE_VALUE="apply"
  DEFAULT_MAX_CREATE="4"
else
  MODE_VALUE="dry-run"
  DEFAULT_MAX_CREATE="0"
fi
MAX_CREATE_VALUE="${MAX_CREATE:-$DEFAULT_MAX_CREATE}"

set_var() {
  local name="$1"
  local value="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] gh variable set $name --repo $REPO --body '$value'"
    return 0
  fi
  gh variable set "$name" --repo "$REPO" --body "$value"
}

delete_var() {
  local name="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] gh variable delete $name --repo $REPO"
    return 0
  fi
  gh variable delete "$name" --repo "$REPO" >/dev/null 2>&1 || true
}

set_var "PM_CYCLE_MODE" "$MODE_VALUE"
set_var "PM_CYCLE_MAX_CREATE" "$MAX_CREATE_VALUE"

if [[ -n "$COMMENT_ISSUE" ]]; then
  set_var "PM_CYCLE_ISSUE_NUMBER" "$COMMENT_ISSUE"
elif [[ "$CLEAR_COMMENT_ISSUE" -eq 1 ]]; then
  delete_var "PM_CYCLE_ISSUE_NUMBER"
fi

echo "PM dual-lane mode updated."
echo "- repo: $REPO"
echo "- lane: $LANE"
echo "- PM_CYCLE_MODE=$MODE_VALUE"
echo "- PM_CYCLE_MAX_CREATE=$MAX_CREATE_VALUE"
if [[ -n "$COMMENT_ISSUE" ]]; then
  echo "- PM_CYCLE_ISSUE_NUMBER=$COMMENT_ISSUE"
elif [[ "$CLEAR_COMMENT_ISSUE" -eq 1 ]]; then
  echo "- PM_CYCLE_ISSUE_NUMBER=(deleted)"
fi

#!/usr/bin/env bash
set -euo pipefail

KIND="pm"
INPUT=""
OUTPUT=""
DECISION="cycle_summary_post"
NEXT_STATUS="status/in-progress"
TITLE="[PM AUTO][CYCLE SUMMARY]"
VALIDATE_ONLY="false"

usage() {
  cat <<'USAGE'
Usage:
  comment_template.sh --kind pm --input <file> [--output <file>]
                      [--decision <text>] [--next-status <label>] [--title <text>]
                      [--validate-only]

Examples:
  bash scripts/pm/comment_template.sh --kind pm --input reports/pm/pm_cycle_apply_20260227_120000.md --output /tmp/pm_comment.md
  bash scripts/pm/comment_template.sh --kind pm --input /tmp/pm_comment.md --validate-only
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind)
      KIND="${2:-}"
      shift 2
      ;;
    --input)
      INPUT="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --decision)
      DECISION="${2:-}"
      shift 2
      ;;
    --next-status)
      NEXT_STATUS="${2:-}"
      shift 2
      ;;
    --title)
      TITLE="${2:-}"
      shift 2
      ;;
    --validate-only)
      VALIDATE_ONLY="true"
      shift 1
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

if [[ "$KIND" != "pm" ]]; then
  echo "Unsupported --kind: $KIND (only pm is supported)" >&2
  exit 1
fi
if [[ -z "$INPUT" ]]; then
  echo "Missing required --input" >&2
  exit 1
fi
if [[ ! -f "$INPUT" ]]; then
  echo "Input file not found: $INPUT" >&2
  exit 1
fi

has_key() {
  local key="$1"
  local text="$2"
  printf "%s" "$text" | grep -Eiq "(^|[[:space:]])${key}[[:space:]]*:"
}

starts_with_pm_header() {
  local text="$1"
  printf "%s" "$text" | grep -Eiq "^[[:space:]]*\\[PM[^]]*\\]"
}

validate_pm_comment() {
  local text="$1"
  local errors=()
  if starts_with_pm_header "$text"; then
    if ! has_key "decision" "$text"; then
      errors+=("missing key: decision:")
    fi
    if ! has_key "next_status" "$text"; then
      errors+=("missing key: next_status:")
    fi
  fi
  if [[ ${#errors[@]} -gt 0 ]]; then
    {
      echo "[CONTRACT FAIL][PM COMMENT TEMPLATE]"
      for e in "${errors[@]}"; do
        echo "- ${e}"
      done
    } >&2
    return 1
  fi
  return 0
}

body="$(cat "$INPUT")"

if [[ "$VALIDATE_ONLY" == "true" ]]; then
  validate_pm_comment "$body"
  exit 0
fi

prefix_lines=()
if ! starts_with_pm_header "$body"; then
  prefix_lines+=("$TITLE")
fi
if ! has_key "decision" "$body"; then
  prefix_lines+=("decision: ${DECISION}")
fi
if ! has_key "next_status" "$body"; then
  prefix_lines+=("next_status: ${NEXT_STATUS}")
fi

rendered="$body"
if [[ ${#prefix_lines[@]} -gt 0 ]]; then
  header_block="$(printf "%s\n" "${prefix_lines[@]}")"
  if [[ -n "$body" ]]; then
    rendered="${header_block}"$'\n'"${body}"
  else
    rendered="${header_block}"
  fi
fi

validate_pm_comment "$rendered"

if [[ -n "$OUTPUT" ]]; then
  printf "%s\n" "$rendered" > "$OUTPUT"
else
  printf "%s\n" "$rendered"
fi

#!/usr/bin/env bash
set -euo pipefail

REPO=""
DATE_FILTER=""
COMMENT_ISSUE=""
LIMIT=200
MODE="dry-run"   # dry-run | apply
MAX_CREATE=4
ALLOW_REOPEN_DONE_RAW="${PM_CYCLE_ALLOW_REOPEN_DONE:-false}"
REOPEN_LOOKBACK_DAYS="${PM_CYCLE_REOPEN_LOOKBACK_DAYS:-7}"

usage() {
  cat <<USAGE
Usage: $0 --repo <owner/repo> [--date YYYY-MM-DD] [--comment-issue <number>] [--mode dry-run|apply] [--max-create N]
          [--allow-reopen-done true|false] [--reopen-lookback-days N]

- dry-run: 이슈 변경 없이 PM 요약/제안만 생성
- apply: QA 게이트/리마인드/QA FAIL 후속이슈 자동 반영
- 출력 파일: reports/pm/pm_cycle_<mode>_<UTC timestamp>.md
- reopen 기본정책: PM_CYCLE_ALLOW_REOPEN_DONE=false (명시적 opt-in일 때만 reopen)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --date)
      DATE_FILTER="${2:-}"
      shift 2
      ;;
    --comment-issue)
      COMMENT_ISSUE="${2:-}"
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --max-create)
      MAX_CREATE="${2:-}"
      shift 2
      ;;
    --allow-reopen-done)
      ALLOW_REOPEN_DONE_RAW="${2:-}"
      shift 2
      ;;
    --reopen-lookback-days)
      REOPEN_LOOKBACK_DAYS="${2:-}"
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

if [[ -z "$REPO" ]]; then
  echo "Missing required --repo <owner/repo>"
  exit 1
fi
if [[ "$MODE" != "dry-run" && "$MODE" != "apply" ]]; then
  echo "Invalid --mode: $MODE (use dry-run|apply)"
  exit 1
fi
if ! [[ "$MAX_CREATE" =~ ^[0-9]+$ ]]; then
  echo "Invalid --max-create: $MAX_CREATE"
  exit 1
fi
if ! [[ "$REOPEN_LOOKBACK_DAYS" =~ ^[0-9]+$ ]]; then
  echo "Invalid --reopen-lookback-days: $REOPEN_LOOKBACK_DAYS"
  exit 1
fi

normalize_bool() {
  local raw="${1:-}"
  local lowered
  lowered="$(echo "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$lowered" in
    1|true|yes|on)
      echo "true"
      ;;
    0|false|no|off|"")
      echo "false"
      ;;
    *)
      echo "false"
      ;;
  esac
}

ALLOW_REOPEN_DONE="$(normalize_bool "$ALLOW_REOPEN_DONE_RAW")"

for cmd in gh jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd is required"
    exit 1
  fi
done

TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TODAY_UTC="$(date -u +%Y-%m-%d)"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT_DIR="reports/pm"
MODE_SLUG="${MODE//-/_}"
OUT_FILE="${OUT_DIR}/pm_cycle_${MODE_SLUG}_${STAMP}.md"
mkdir -p "$OUT_DIR"

DIRS=("UIUX_reports" "Collector_reports" "develop_report" "QA_reports")
REPORT_PATTERN="*_report.md"
if [[ -n "$DATE_FILTER" ]]; then
  REPORT_PATTERN="${DATE_FILTER}_*_report.md"
fi

suggest_owner_from_path() {
  local path="$1"
  case "$path" in
    apps/web/*|UIUX_reports/*)
      echo "role/uiux"
      ;;
    src/pipeline/*|Collector_reports/*)
      echo "role/collector"
      ;;
    app/*|db/*|scripts/qa/*|develop_report/*|tests/*)
      echo "role/develop"
      ;;
    *)
      echo "role/develop"
      ;;
  esac
}

extract_primary_path() {
  local file="$1"
  grep -Eo '([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\.(py|ts|tsx|js|md|sql|sh))(:[0-9]+)?' "$file" | head -n 1 || true
}

is_qa_fail_report() {
  local file="$1"
  if python3 scripts/pm/qafail_detection.py --file "$file" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

has_qa_pass_comment() {
  local issue_no="$1"
  local issue_json
  issue_json="$(gh issue view "$issue_no" --repo "$REPO" --json comments 2>/dev/null || true)"
  [[ -n "$issue_json" ]] || return 1
  if printf "%s" "$issue_json" | python3 scripts/pm/qapass_detection.py --mode issue-json >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

gh auth status >/dev/null 2>&1

ALL_ISSUES_JSON="$(gh issue list --repo "$REPO" --state all --limit "$LIMIT" --json number,title,state,labels,updatedAt,url)"
OPEN_ISSUES_JSON="$(gh issue list --repo "$REPO" --state open --limit "$LIMIT" --json number,title,state,labels,updatedAt,url)"
LABELS_JSON="$(gh label list --repo "$REPO" --limit 200 --json name)"

TOTAL_COUNT="$(echo "$ALL_ISSUES_JSON" | jq 'length')"
OPEN_COUNT="$(echo "$OPEN_ISSUES_JSON" | jq 'length')"
CLOSED_COUNT=$((TOTAL_COUNT - OPEN_COUNT))

role_open_count() {
  local role="$1"
  echo "$OPEN_ISSUES_JSON" | jq --arg role "$role" '[.[] | select(([.labels[].name] | index($role)))] | length'
}

ROLE_UIUX_OPEN="$(role_open_count "role/uiux")"
ROLE_COLLECTOR_OPEN="$(role_open_count "role/collector")"
ROLE_DEVELOP_OPEN="$(role_open_count "role/develop")"
ROLE_QA_OPEN="$(role_open_count "role/qa")"

BLOCKED_OPEN="$(echo "$OPEN_ISSUES_JSON" | jq '[.[] | select(([.labels[].name] | index("status/blocked")))] | length')"
READY_OPEN="$(echo "$OPEN_ISSUES_JSON" | jq '[.[] | select(([.labels[].name] | index("status/ready")))] | length')"

REOPEN_ELIGIBLE=()
while IFS= read -r issue_no; do
  [[ -z "$issue_no" ]] && continue
  REOPEN_ELIGIBLE+=("$issue_no")
done < <(echo "$ALL_ISSUES_JSON" | python3 scripts/pm/reopen_policy.py \
  --allow-reopen-done "$ALLOW_REOPEN_DONE" \
  --lookback-days "$REOPEN_LOOKBACK_DAYS" \
  --now "$TIMESTAMP_UTC")

MISSING_QA_PASS=()
if [[ "${#REOPEN_ELIGIBLE[@]}" -gt 0 ]]; then
  while IFS= read -r issue_no; do
    [[ -z "$issue_no" ]] && continue
    if ! has_qa_pass_comment "$issue_no"; then
      MISSING_QA_PASS+=("$issue_no")
    fi
  done < <(printf "%s\n" "${REOPEN_ELIGIBLE[@]}")
fi

HAS_ROLE_QA="no"
HAS_STATUS_IN_QA="no"
if echo "$LABELS_JSON" | jq -e '[.[].name] | index("role/qa")' >/dev/null; then
  HAS_ROLE_QA="yes"
fi
if echo "$LABELS_JSON" | jq -e '[.[].name] | index("status/in-qa")' >/dev/null; then
  HAS_STATUS_IN_QA="yes"
fi

REQUIRED_CI_SECRETS=(
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  DATA_GO_KR_KEY
  DATABASE_URL
  INTERNAL_JOB_TOKEN
)
SECRET_HEALTH_STATUS="unavailable"
MISSING_CI_SECRETS=()
if SECRETS_JSON="$(gh secret list --repo "$REPO" --json name 2>/dev/null)"; then
  SECRET_HEALTH_STATUS="ok"
  for s in "${REQUIRED_CI_SECRETS[@]}"; do
    if ! echo "$SECRETS_JSON" | jq -e --arg s "$s" '[.[].name] | index($s)' >/dev/null; then
      MISSING_CI_SECRETS+=("$s")
    fi
  done
  if [[ "${#MISSING_CI_SECRETS[@]}" -gt 0 ]]; then
    SECRET_HEALTH_STATUS="missing"
  fi
fi

APPLIED_ACTIONS=()
CREATED_COUNT=0
MODE_TITLE="Dry Run"
if [[ "$MODE" == "apply" ]]; then
  MODE_TITLE="Apply"
fi

if [[ "$MODE" == "apply" ]]; then
  # 1) QA gate backfill: explicit opt-in + filtered done+closed without QA PASS
  if [[ "$ALLOW_REOPEN_DONE" == "true" ]]; then
    for n in "${MISSING_QA_PASS[@]}"; do
      gh issue edit "$n" --repo "$REPO" --add-label "status/in-qa" >/dev/null
      gh issue edit "$n" --repo "$REPO" --remove-label "status/done" >/dev/null || true
      gh issue reopen "$n" --repo "$REPO" >/dev/null || true
      gh issue comment "$n" --repo "$REPO" --body "[PM AUTO][QA GATE]\nauto_key: qa-gate-${n}-${TODAY_UTC}\n\n해당 이슈는 \`status/done\` 상태였지만 \`[QA PASS]\` 코멘트가 확인되지 않아 \`status/in-qa\`로 복귀되었습니다." >/dev/null
      APPLIED_ACTIONS+=("qa_gate_reopen:#${n}")
    done
  else
    APPLIED_ACTIONS+=("qa_gate_reopen_skipped:allow_reopen_done=false")
  fi

  # 2) blocked open issue daily nudge (idempotent by auto_key)
  while IFS= read -r blocked_no; do
    [[ -z "$blocked_no" ]] && continue
    key="blocked-nudge-${blocked_no}-${TODAY_UTC}"
    comments="$(gh issue view "$blocked_no" --repo "$REPO" --json comments --jq '.comments[].body' || true)"
    if ! printf "%s" "$comments" | grep -q "$key"; then
      gh issue comment "$blocked_no" --repo "$REPO" --body "[PM AUTO][BLOCKED NUDGE]\nauto_key: ${key}\n\n차단 상태가 유지 중입니다. 차단 원인/해소 조건/필요 권한을 업데이트해주세요." >/dev/null
      APPLIED_ACTIONS+=("blocked_nudge:#${blocked_no}")
    fi
  done < <(echo "$OPEN_ISSUES_JSON" | jq -r '.[] | select(([.labels[].name] | index("status/blocked"))) | .number')

  # 3) QA FAIL report -> follow-up issue auto create (dedup by auto_key)
  if [[ -d "QA_reports" ]]; then
    while IFS= read -r qa_file; do
      [[ -z "$qa_file" ]] && continue
      is_qa_fail_report "$qa_file" || continue
      if [[ "$CREATED_COUNT" -ge "$MAX_CREATE" ]]; then
        APPLIED_ACTIONS+=("qa_followup_skipped:max_create_reached")
        break
      fi

      base="$(basename "$qa_file" .md)"
      auto_key="qa-fail-${base}"
      existing="$(gh issue list --repo "$REPO" --state open --search "in:body ${auto_key}" --limit 1 --json number | jq 'length')"
      if [[ "$existing" -gt 0 ]]; then
        APPLIED_ACTIONS+=("qa_followup_exists:${auto_key}")
        continue
      fi

      root_path="$(extract_primary_path "$qa_file")"
      owner_label="$(suggest_owner_from_path "$root_path")"
      title="[AUTO][QA FAIL] ${base}"
      body=$(cat <<EOF
Goal
- QA FAIL 보고서 기반 후속 수정 작업 생성

Auto-Key
- ${auto_key}

Source
- Report-Path: ${qa_file}
- Root-Cause-Path: ${root_path:-unknown}
- Suggested-Owner: ${owner_label}

DoD
- [ ] QA FAIL 재현
- [ ] 원인 수정 반영
- [ ] QA 재검증에서 [QA PASS] 획득
EOF
)
      ASSIGNEE_ARGS=()
      if ME_LOGIN="$(gh api user --jq '.login' 2>/dev/null)"; then
        if [[ "$ME_LOGIN" != "github-actions[bot]" ]] && gh api "repos/${REPO}/assignees/${ME_LOGIN}" >/dev/null 2>&1; then
          ASSIGNEE_ARGS=(--assignee "$ME_LOGIN")
        else
          APPLIED_ACTIONS+=("qa_followup_unassigned:${auto_key}")
        fi
      fi
      gh issue create \
        --repo "$REPO" \
        --title "$title" \
        --body "$body" \
        --label "$owner_label" \
        --label "type/bug" \
        --label "status/backlog" \
        --label "priority/p1" \
        "${ASSIGNEE_ARGS[@]}" >/dev/null
      CREATED_COUNT=$((CREATED_COUNT + 1))
      APPLIED_ACTIONS+=("qa_followup_created:${auto_key}")
    done < <(find "QA_reports" -maxdepth 1 -type f -name "$REPORT_PATTERN" | sort)
  fi
fi

{
  echo "# PM Cycle ${MODE_TITLE}"
  echo "- generated_at_utc: ${TIMESTAMP_UTC}"
  echo "- repo: ${REPO}"
  if [[ -n "$DATE_FILTER" ]]; then
    echo "- report_date_filter: ${DATE_FILTER}"
  else
    echo "- report_date_filter: (none)"
  fi
  echo "- mode: ${MODE}"
  echo
  echo "## Snapshot"
  echo "- total_issues: ${TOTAL_COUNT}"
  echo "- closed_issues: ${CLOSED_COUNT}"
  echo "- open_issues: ${OPEN_COUNT}"
  echo "- blocked_open_issues: ${BLOCKED_OPEN}"
  echo "- ready_open_issues: ${READY_OPEN}"
  echo
  echo "## Open By Role"
  echo "- role/uiux: ${ROLE_UIUX_OPEN}"
  echo "- role/collector: ${ROLE_COLLECTOR_OPEN}"
  echo "- role/develop: ${ROLE_DEVELOP_OPEN}"
  echo "- role/qa: ${ROLE_QA_OPEN}"
  echo
  echo "## Label Health"
  echo "- role/qa label: ${HAS_ROLE_QA}"
  echo "- status/in-qa label: ${HAS_STATUS_IN_QA}"
  echo
  echo "## Secret Health (Review)"
  echo "- status: ${SECRET_HEALTH_STATUS}"
  if [[ "$SECRET_HEALTH_STATUS" == "missing" ]]; then
    echo "- missing_required_secrets:"
    for s in "${MISSING_CI_SECRETS[@]}"; do
      echo "  - ${s}"
    done
  elif [[ "$SECRET_HEALTH_STATUS" == "unavailable" ]]; then
    echo "- note: secret list 조회 권한이 없어 점검 불가"
  else
    echo "- missing_required_secrets: 0"
  fi
  echo
  echo "## Open Issue Queue"
  if [[ "$OPEN_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    echo "$OPEN_ISSUES_JSON" | jq -r '.[] | "- [#\(.number)](\(.url)) \(.title)"'
  fi
  echo
  echo "## Latest Reports"
  for dir in "${DIRS[@]}"; do
    if [[ ! -d "$dir" ]]; then
      echo "- ${dir}: (missing directory)"
      continue
    fi
    latest_file="$(find "$dir" -maxdepth 1 -type f -name "$REPORT_PATTERN" | sort | tail -n 1 || true)"
    if [[ -z "$latest_file" ]]; then
      echo "- ${dir}: (no matching report)"
    else
      echo "- ${dir}: \`${latest_file}\`"
    fi
  done
  echo
  echo "## QA Reassignment Hints"
  QA_FOUND=0
  if [[ -d "QA_reports" ]]; then
    while IFS= read -r qa_file; do
      [[ -z "$qa_file" ]] && continue
      QA_FOUND=1
      root_path="$(extract_primary_path "$qa_file")"
      if [[ -n "$root_path" ]]; then
        suggested_owner="$(suggest_owner_from_path "$root_path")"
      else
        suggested_owner="role/develop"
      fi
      echo "- \`${qa_file}\`: root_cause=\`${root_path:-unknown}\`, suggested_reassign=\`${suggested_owner}\`"
    done < <(find "QA_reports" -maxdepth 1 -type f -name "$REPORT_PATTERN" | sort)
  fi
  if [[ "$QA_FOUND" -eq 0 ]]; then
    echo "- (no QA reports matched)"
  fi
  echo
  echo "## Gate Checks"
  echo "- reopen_policy_enabled: ${ALLOW_REOPEN_DONE}"
  echo "- reopen_lookback_days: ${REOPEN_LOOKBACK_DAYS}"
  echo "- reopen_candidates_checked: ${#REOPEN_ELIGIBLE[@]}"
  if [[ "${#MISSING_QA_PASS[@]}" -eq 0 ]]; then
    echo "- closed+done without [QA PASS]: 0"
  else
    echo "- closed+done without [QA PASS]: ${#MISSING_QA_PASS[@]}"
    for n in "${MISSING_QA_PASS[@]}"; do
      issue_url="$(echo "$ALL_ISSUES_JSON" | jq -r --arg n "$n" '.[] | select((.number|tostring)==$n) | .url')"
      issue_title="$(echo "$ALL_ISSUES_JSON" | jq -r --arg n "$n" '.[] | select((.number|tostring)==$n) | .title')"
      echo "  - [#${n}](${issue_url}) ${issue_title}"
    done
  fi
  echo
  echo "## Applied Actions"
  if [[ "${#APPLIED_ACTIONS[@]}" -eq 0 ]]; then
    echo "- (none)"
  else
    for a in "${APPLIED_ACTIONS[@]}"; do
      echo "- ${a}"
    done
  fi
  echo
  echo "## Suggested Next Actions"
  echo "1. blocked 이슈 우선 해소 후 ready 이슈 순차 진행"
  echo "2. QA FAIL 보고서는 auto_key 기반 중복 없이 후속 이슈 생성"
  echo "3. done 이슈 자동 재오픈은 PM_CYCLE_ALLOW_REOPEN_DONE=true 를 명시한 단발성 apply에서만 사용"
} > "$OUT_FILE"

echo "Wrote: ${OUT_FILE}"

if [[ -n "$COMMENT_ISSUE" ]]; then
  COMMENT_BODY_FILE="${OUT_FILE%.md}_comment.md"
  if ! bash scripts/pm/comment_template.sh \
      --kind pm \
      --input "$OUT_FILE" \
      --output "$COMMENT_BODY_FILE" \
      --decision "cycle_${MODE}_summary_posted" \
      --next-status "status/in-progress"; then
    echo "WARN: PM comment template generation failed. Skip comment post to issue #${COMMENT_ISSUE}."
    exit 0
  fi

  if ! bash scripts/pm/comment_template.sh --kind pm --input "$COMMENT_BODY_FILE" --validate-only; then
    echo "WARN: PM comment schema validation failed. Skip comment post to issue #${COMMENT_ISSUE}."
    exit 0
  fi

  gh issue comment "$COMMENT_ISSUE" --repo "$REPO" --body-file "$COMMENT_BODY_FILE"
  echo "Commented cycle summary to issue #${COMMENT_ISSUE}"
fi

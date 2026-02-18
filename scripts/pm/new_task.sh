#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <repo> <role:uiux|collector|develop> <title> <assignee> [priority:p0|p1|p2] [milestone]"
  exit 1
fi

REPO="$1"
ROLE="$2"
TITLE="$3"
ASSIGNEE="$4"
PRIORITY="${5:-p1}"
MILESTONE="${6:-Sprint-Week1-MVP}"

case "$ROLE" in
  uiux)
    ROLE_LABEL="role/uiux"
    REPORT_PREFIX="UIUX_reports"
    ;;
  collector)
    ROLE_LABEL="role/collector"
    REPORT_PREFIX="Collector_reports"
    ;;
  develop)
    ROLE_LABEL="role/develop"
    REPORT_PREFIX="develop_report"
    ;;
  *)
    echo "Invalid role: $ROLE"
    exit 1
    ;;
esac

DATE="$(date +%F)"
BODY=$(cat <<EOB
## Goal
- 

## Scope
- 

## DoD
- [ ] 구현/문서/테스트 반영
- [ ] 보고서 제출

## Report-Path
Report-Path: ${REPORT_PREFIX}/${DATE}_<topic>_report.md
EOB
)

gh issue create \
  --repo "$REPO" \
  --title "[$(echo "$ROLE" | tr '[:lower:]' '[:upper:]')] $TITLE" \
  --assignee "$ASSIGNEE" \
  --milestone "$MILESTONE" \
  --label "$ROLE_LABEL" \
  --label "type/task" \
  --label "status/backlog" \
  --label "priority/${PRIORITY}" \
  --body "$BODY"

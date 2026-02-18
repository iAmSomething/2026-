#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <repo> <role:uiux|collector|develop|qa> <title> <assignee> [priority:p0|p1|p2] [milestone]"
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
    LOCK_SCOPE='- [ ] UIUX 작업영역(`apps/web/**`, `UIUX_reports/**`, `poll_uiux_docs_v0.1/**`) 안에서만 수행'
    ;;
  collector)
    ROLE_LABEL="role/collector"
    REPORT_PREFIX="Collector_reports"
    LOCK_SCOPE='- [ ] Collector 작업영역(`src/pipeline/**`, `Collector_reports/**`, `data/**`) 안에서만 수행'
    ;;
  develop)
    ROLE_LABEL="role/develop"
    REPORT_PREFIX="develop_report"
    LOCK_SCOPE='- [ ] Develop 작업영역(`app/**`, `db/**`, `develop_report/**`, `scripts/qa/**`) 안에서만 수행'
    ;;
  qa)
    ROLE_LABEL="role/qa"
    REPORT_PREFIX="QA_reports"
    LOCK_SCOPE='- [ ] QA 작업영역(`QA_reports/**`, `tests/**`, `scripts/qa/**`) 안에서만 수행'
    ;;
  *)
    echo "Invalid role: $ROLE"
    exit 1
    ;;
esac

DATE="$(date +%F)"
REPORT_SUFFIX="<topic>"
if [ "$ROLE" = "qa" ]; then
  REPORT_SUFFIX="qa_<topic>"
fi

COMMON_DOD=$(cat <<EOD
- [ ] 구현/문서/테스트 반영
- [ ] 보고서 제출
- [ ] 구현 이슈는 QA PASS 코멘트 확인 후 Done 처리
EOD
)

if [ "$ROLE" = "qa" ]; then
  ROLE_DOD=$(cat <<EOD
- [ ] PASS/WARN/FAIL 판정 및 근거 첨부
- [ ] 실패 원인(파일/라인)과 재현 시나리오 명시
- [ ] 담당자 재할당 제안 포함
EOD
)
else
  ROLE_DOD="$COMMON_DOD"
fi

BODY=$(cat <<EOB
## Goal
- 

## Scope
- 

## Workspace Lock Checklist
$LOCK_SCOPE
- [ ] 공용 잠금 경로(\`docs/**\`, \`.github/**\`, \`scripts/pm/**\`, \`README.md\`) 수정 시 PM 승인 코멘트 링크 첨부
- [ ] 충돌 가능 파일은 이슈 코멘트로 선점 선언 완료

## DoD
$ROLE_DOD

## Report-Path
Report-Path: ${REPORT_PREFIX}/${DATE}_${REPORT_SUFFIX}_report.md
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

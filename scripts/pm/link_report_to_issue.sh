#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <repo> <issue-number> <report-path> [note]"
  exit 1
fi

REPO="$1"
ISSUE_NO="$2"
REPORT_PATH="$3"
NOTE="${4:-}"

if [ ! -f "$REPORT_PATH" ]; then
  echo "report file not found: $REPORT_PATH"
  exit 1
fi

if ! [[ "$REPORT_PATH" =~ ^(UIUX_reports|Collector_reports|develop_report)/[0-9]{4}-[0-9]{2}-[0-9]{2}_.+_report\.md$ ]]; then
  echo "invalid report path format: $REPORT_PATH"
  exit 1
fi

BODY="Report-Path: ${REPORT_PATH}"
if [ -n "$NOTE" ]; then
  BODY+=$'\n\n'
  BODY+="$NOTE"
fi

gh issue comment "$ISSUE_NO" --repo "$REPO" --body "$BODY"
echo "linked report to issue #$ISSUE_NO"

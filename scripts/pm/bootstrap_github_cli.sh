#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
OWNER="${REPO%%/*}"

upsert_label() {
  local name="$1" color="$2" desc="$3"
  if gh label create "$name" --color "$color" --description "$desc" --repo "$REPO" 2>/dev/null; then
    echo "created label: $name"
  else
    gh label edit "$name" --color "$color" --description "$desc" --repo "$REPO"
    echo "updated label: $name"
  fi
}

upsert_variable() {
  local name="$1" value="$2"
  if gh variable set "$name" --repo "$REPO" --body "$value" >/dev/null 2>&1; then
    echo "upserted variable: $name=$value"
  else
    echo "skip variable setup: $name (missing repo variable permission)"
  fi
}

echo "[1/4] labels setup for $REPO"
upsert_label "role/uiux" "1d76db" "UIUX owner"
upsert_label "role/collector" "5319e7" "Collector owner"
upsert_label "role/develop" "0e8a16" "Develop owner"

upsert_label "status/backlog" "ededed" "Backlog"
upsert_label "status/ready" "fbca04" "Ready"
upsert_label "status/in-progress" "0052cc" "In progress"
upsert_label "status/blocked" "d93f0b" "Blocked"
upsert_label "status/in-review" "c2e0c6" "In review"
upsert_label "status/done" "0e8a16" "Done"

upsert_label "priority/p0" "b60205" "Highest priority"
upsert_label "priority/p1" "d93f0b" "High priority"
upsert_label "priority/p2" "fbca04" "Normal priority"

upsert_label "type/task" "a2eeef" "Task"
upsert_label "type/bug" "d73a4a" "Bug"
upsert_label "type/chore" "cfd3d7" "Chore"

echo "[2/4] milestone setup"
if gh api "repos/$REPO/milestones" --jq '.[].title' | grep -Fx "Sprint-Week1-MVP" >/dev/null 2>&1; then
  echo "milestone exists: Sprint-Week1-MVP"
else
  gh api "repos/$REPO/milestones" -f title='Sprint-Week1-MVP' -f state='open' >/dev/null
  echo "created milestone: Sprint-Week1-MVP"
fi

echo "[3/4] project setup (optional, requires read:project/project scopes)"
if gh project list --owner "$OWNER" >/dev/null 2>&1; then
  if gh project list --owner "$OWNER" | grep -F "Election 2026 Delivery" >/dev/null 2>&1; then
    echo "project exists: Election 2026 Delivery"
  else
    gh project create --owner "$OWNER" --title "Election 2026 Delivery" >/dev/null
    echo "created project: Election 2026 Delivery"
  fi
else
  echo "skip project setup: missing project scopes"
  echo "run: gh auth refresh -s read:project -s project"
fi

echo "[4/4] PM cycle default variables"
upsert_variable "PM_CYCLE_MODE" "dry-run"
upsert_variable "PM_CYCLE_MAX_CREATE" "4"
upsert_variable "PM_CYCLE_ALLOW_REOPEN_DONE" "false"
upsert_variable "PM_CYCLE_REOPEN_LOOKBACK_DAYS" "7"

echo "bootstrap complete"

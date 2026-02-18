# 2026-02-19 Hotfix Schedule Workflows Recovery Report (Issue #44)

## 1) Incident
1. Ingest Schedule 실패
- 증상: `ModuleNotFoundError: No module named 'app'`
- 원인: `scripts/qa/run_ingest_with_retry.py` 실행 시 repo root가 `sys.path`에 보장되지 않음

2. PM Cycle 실패
- 증상: `could not assign user: 'github-actions[bot]' not found`
- 원인: `scripts/pm/pm_cycle_dry_run.sh`가 `gh issue create --assignee "@me"`를 강제

## 2) Fix
1. `scripts/qa/run_ingest_with_retry.py`
- `Path(__file__).resolve().parents[2]`를 repo root로 계산
- root를 `sys.path`에 삽입하여 CI 환경에서도 `from app...` import 동작 보장

2. `scripts/pm/pm_cycle_dry_run.sh`
- `--assignee "@me"` 제거
- assignee 후보(`gh api user`)가 `github-actions[bot]`이거나 assign 불가일 경우 unassigned fallback

## 3) Local Verification
1. `python3 -m py_compile scripts/qa/run_ingest_with_retry.py` 통과
2. `bash -n scripts/pm/pm_cycle_dry_run.sh` 통과

## 4) Remote Verification
1. PR/merge 후 `workflow_dispatch`로 아래 워크플로 검증 예정
- Ingest Schedule
- PM Cycle
2. Green run 링크는 이슈 코멘트에 첨부

## 5) 재발 방지
1. CI/automation 스크립트의 import 경로는 실행 위치 의존성을 제거(`sys.path` root bootstrap)
2. GitHub Actions actor 기반 assign은 optional 처리하고 실패 시 무할당으로 계속 진행

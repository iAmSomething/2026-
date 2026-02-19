# 2026-02-19 Hotfix Schedule Workflows Recovery Report

## 1) 이슈
- 대상: `#44 [DEVELOP] 긴급핫픽스: Ingest Schedule/PM Cycle 스케줄 실패 복구`
- Report-Path: `develop_report/2026-02-19_hotfix_schedule_workflows_recovery_report.md`

## 2) 장애 원인
1. Ingest Schedule
- 증상: `ModuleNotFoundError: No module named 'app'`
- 원인: `scripts/qa/run_ingest_with_retry.py` 실행 시 repo root가 import path에 보장되지 않음

2. PM Cycle
- 증상: `could not assign user: 'github-actions[bot]' not found`
- 원인: `scripts/pm/pm_cycle_dry_run.sh`에서 `gh issue create --assignee "@me"`를 강제

## 3) 수정 사항
1. `scripts/qa/run_ingest_with_retry.py`
- `ROOT = Path(__file__).resolve().parents[2]`
- `sys.path`에 root 삽입 후 `from app.jobs...` import

2. `scripts/pm/pm_cycle_dry_run.sh`
- assignee를 고정하지 않고 `ASSIGNEE_ARGS` 동적 구성
- actor가 `github-actions[bot]`이거나 assign 불가면 unassigned fallback

## 4) 로컬 검증
1. `python3 -m py_compile scripts/qa/run_ingest_with_retry.py` 통과
2. `bash -n scripts/pm/pm_cycle_dry_run.sh` 통과

## 5) 원격 검증 계획
1. PR 머지 후 `workflow_dispatch` 실행
- `Ingest Schedule` 1회 green 확인
- `PM Cycle` 1회 green 확인
2. 이후 scheduled run 1회 green 확인 후 이슈 종료

## 6) 재발 방지
1. CI용 Python 스크립트는 실행 디렉토리 의존 import를 금지하고 root bootstrap을 기본화
2. GitHub Actions 계정 기반 assignee는 best-effort로 처리하고 실패 시 무할당으로 진행

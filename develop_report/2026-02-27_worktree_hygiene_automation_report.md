# 2026-02-27 Worktree Hygiene Automation Report

## 1) 작업 개요
- 대상 이슈: `#471` `[DEVELOP][P1] worktree/runtime 임시폴더 자동정리 가드 도입`
- 목표:
  1. 24h 이상 미접근 임시 worktree/runtime 폴더 후보 탐지
  2. 안전 제외(메인 레포/활성 worktree) 적용
  3. `dry-run` / `apply` 모드 지원
  4. 수동 + 주간 자동 리포트 워크플로 구축

## 2) 구현 변경 사항
1. 스크립트 추가: `/scripts/pm/worktree_hygiene.sh`
- 지원 옵션:
  - `--mode dry-run|apply`
  - `--hours <stale_threshold>`
  - `--base-dir <scan_base>`
  - `--report <output_path>`
- 탐지 패턴:
  - `election2026_codex`
  - `election2026_codex_issue*`
  - `election2026_issue*`
  - `election2026_runtime*`
  - `election2026_codex_runtime*`
- 안전 제외 정책:
  - `election2026_codex` (protected root)
  - `git worktree list --porcelain` 기반 활성 worktree 경로
- 적용 시 가드:
  - `base_dir` 하위 + 관리 패턴 경로만 삭제 허용
- 산출 리포트:
  - 후보/제외/삭제/오류 목록 + count 집계 기록

2. 테스트 추가: `/tests/test_worktree_hygiene_script.py`
- `dry-run`: stale 비활성 경로만 후보로 잡히는지 검증
- `apply`: guarded candidate만 삭제되고 active worktree는 유지되는지 검증

3. GitHub Action 추가: `/.github/workflows/worktree-hygiene.yml`
- 트리거:
  - `workflow_dispatch` (수동)
  - `schedule` (주 1회, 월요일 01:00 UTC)
- 동작:
  - 스케줄 실행은 강제 `dry-run`
  - 실행 결과 리포트를 artifact로 업로드

4. 운영 문서 반영: `/docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`
- Worktree/Runtime 위생 규칙, 로컬 실행 명령, 자동화 워크플로 명시

## 3) 검증 결과
1. 단위 테스트
- 명령: `pytest tests/test_worktree_hygiene_script.py -q`
- 결과: `2 passed`

2. 스크립트 실증(demo)
- 동일 입력 디렉터리에서 `dry-run` 후 `apply` 실행
- dry-run 결과: `candidate_count=2`, `deleted_count=0`, `error_count=0`
- apply 결과: `candidate_count=2`, `deleted_count=2`, `error_count=0`
- active worktree 경로는 삭제되지 않고 유지됨

## 4) 수용 기준 매핑
- [x] dry-run 결과와 실제 정리 결과 일치
- [x] 메인 레포/활성 worktree 오삭제 0건
- [x] 보고서 제출 완료

## 5) 의사결정 필요 사항
- 없음.

## 6) 변경 파일
- `/.github/workflows/worktree-hygiene.yml`
- `/scripts/pm/worktree_hygiene.sh`
- `/tests/test_worktree_hygiene_script.py`
- `/docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`
- `/develop_report/2026-02-27_worktree_hygiene_automation_report.md`

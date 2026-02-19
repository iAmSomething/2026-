# 2026-02-19 Dual Lane Ops Mode Report

## 1) 이슈
- 대상: `#51 [DEVELOP] 운영 듀얼레인 모드 구축(오프라인 자동 + 온라인 수동)`
- Report-Path: `develop_report/2026-02-19_dual_lane_ops_mode_report.md`

## 2) 목표
- 오프라인 시간대에는 PM Cycle 자동 반영을 허용하고, 온라인 세션에서는 수동 관제 중심으로 전환하는 운영 표준을 고정한다.

## 3) 변경 내용
1. 운영 모드 스위처 스크립트 반영
- 파일: `scripts/pm/set_pm_cycle_mode.sh`
- 기능:
  - `--lane offline` -> `PM_CYCLE_MODE=apply`, `PM_CYCLE_MAX_CREATE=4`
  - `--lane online` -> `PM_CYCLE_MODE=dry-run`, `PM_CYCLE_MAX_CREATE=0`
  - `--comment-issue`, `--clear-comment-issue`, `--dry-run` 지원

2. 부트스트랩 스크립트 보강
- 파일: `scripts/pm/bootstrap_github_cli.sh`
- 추가:
  - 기본 Repository Variable upsert
    - `PM_CYCLE_MODE=dry-run`
    - `PM_CYCLE_MAX_CREATE=4`
  - 변수 권한 없을 때는 실패 대신 안내 후 계속 진행

3. 운영 문서 표준화
- 파일: `docs/07_GITHUB_CLI_COLLAB_WORKFLOW.md`
- 추가:
  - 듀얼레인 정책(오프라인/온라인 값)
  - 즉시 실행 가능한 CLI 명령 세트
  - 온라인 세션 수동 점검 체크리스트
  - 자동화 상태 변경 허용/금지/재발방지 규칙
- 파일: `docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`
- 추가:
  - 부트스트랩 시 PM 변수 기본값 설명
  - 역할별 설명서 내 듀얼레인 요약/전환 명령

## 4) 검증
1. 스크립트 문법 검사
- `bash -n scripts/pm/set_pm_cycle_mode.sh` 통과
- `bash -n scripts/pm/bootstrap_github_cli.sh` 통과

2. 스위처 동작 시뮬레이션(`--dry-run`)
- `bash scripts/pm/set_pm_cycle_mode.sh --repo iAmSomething/2026- --lane online --dry-run` 실행
- 기대 결과 출력 확인:
  - `PM_CYCLE_MODE=dry-run`
  - `PM_CYCLE_MAX_CREATE=0`

## 5) DoD 대응
1. 온라인/오프라인 운영 절차 문서화
- 충족 (`docs/07_GITHUB_CLI_COLLAB_WORKFLOW.md`, `docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`)

2. 즉시 실행 가능한 CLI 명령 세트 제공
- 충족 (`scripts/pm/set_pm_cycle_mode.sh` + 문서 명령 예시)

3. develop_report 제출
- 충족 (본 문서)

## 6) 운영 시 권장 절차
1. 온라인 세션 시작 시 `--lane online`으로 전환 후 dry-run 점검
2. 상태 변경 필요 시 근거 코멘트 남긴 뒤 `apply` 수동 1회 실행
3. 오프라인 전환 시에만 `--lane offline`으로 자동 반영 재개

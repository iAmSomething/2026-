# 2026-02-23 W4 자동화 스크립트 회귀 테스트 강화 보고서 (#191)

## 1) 목적
- PM Cycle 자동화 스크립트 계열의 회귀 테스트팩을 확장해, lane 전환/QA 판정/재오픈 정책 경계 입력에서의 오동작 위험을 낮춘다.

## 2) 구현 범위
- 신규 테스트 추가:
  - `tests/test_pm_cycle_set_mode_script.py`
- 기존 테스트 확장:
  - `tests/test_pm_cycle_qapass_detection.py`
  - `tests/test_pm_cycle_qafail_detection.py`
  - `tests/test_pm_cycle_reopen_policy.py`

## 3) 세부 반영 내용
1. `set_pm_cycle_mode.sh` 회귀 고정
- offline/online lane의 변수 세팅값 회귀 검증
- `--comment-issue` 반영 검증
- `--clear-comment-issue` 삭제 동작 검증
- `--comment-issue` + `--clear-comment-issue` 충돌 입력 거부 검증

2. QA PASS/FAIL 탐지 경계 케이스 보강
- `comments-array` 모드에서 `[QA PASS]` 인식 테스트 추가
- 라인 시작이 아닌 inline `[QA PASS]` 오탐 방지 검증
- backtick 내 ``[QA FAIL]`` 오탐 방지 검증
- `결론 : Done 처리 불가` 라인 FAIL 탐지 검증

3. Reopen 정책 파싱 보강
- `parse_iso_datetime`의 `Z`/naive timestamp 처리 검증
- `updatedAt` 누락 이슈의 후보 포함 동작 검증

## 4) 검증 결과
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q`
- 결과: `90 passed`

- 명령: `bash scripts/pm/pm_cycle_dry_run.sh --repo iAmSomething/2026- --mode dry-run --max-create 0`
- 결과: 보고서 생성 성공 (`reports/pm/pm_cycle_dry_run_20260223_043134.md`)

## 5) 증빙 파일
- `data/verification/issue191_pm_cycle_regression_pytest.log`
- `data/verification/issue191_pm_cycle_dry_run.log`
- `data/verification/issue191_pm_cycle_latest_report.md`
- `data/verification/issue191_pm_cycle_regression_sha256.txt`

## 6) 리스크/후속
- 현재 테스트팩은 PM Cycle 제어 스크립트와 탐지 로직 중심으로 확장 완료.
- 후속으로 `pm_cycle_dry_run.sh`의 gh 호출 경로 전체에 대한 stubbing 기반 시나리오 테스트를 별도 이슈로 분리 가능.

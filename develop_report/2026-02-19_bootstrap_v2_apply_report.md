# 2026-02-19 Bootstrap v2 Apply Report

## 1) 이슈
- 대상: `#66 [DEVELOP] 커버리지 배치 v2 실DB 적용 + 전후 비교/idempotent 검증`
- Report-Path: `develop_report/2026-02-19_bootstrap_v2_apply_report.md`

## 2) 입력/실행
1. 입력 파일
- `data/bootstrap_ingest_coverage_v2.json` (100 records)

2. 실DB 적용 실행
- 1차 적용: ingestion_run `#154`
- 2차 적용: ingestion_run `#155`
- idempotent 검증 재적용: ingestion_run `#156`

3. 적용 리포트(산출)
- `data/bootstrap_ingest_coverage_v2_apply_report.json`
- 요약:
  - `success_runs=3`, `failed_runs=0`
  - `idempotent_zero_growth=true`
  - `duplicate_growth_detected=false`

## 3) 전후 비교
1. 비교 파일
- `data/bootstrap_ingest_coverage_v2_before_after.json`

2. v1 기준 대비 개선(`delta_v1_to_v2`)
- `regions_covered`: `+20` (11 -> 31)
- `sido_covered`: `+7` (6 -> 13)
- `observations_total`: `+92` (102 -> 194)

## 4) idempotent 검증
- 검증 구간: reapply 전후 비교(`before_reapply` vs `after_reapply`)
- 결과 (`delta`):
  - `regions_total`: `0`
  - `regions_covered`: `0`
  - `sido_covered`: `0`
  - `observations_total`: `0`
- 판정: `all_zero_growth=true`

## 5) 계약/회귀 테스트
1. 회귀
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_bootstrap_ingest.py`
- 결과: `8 passed`

2. 계약
- `bash scripts/qa/run_api_contract_suite.sh --report /tmp/qa_api_contract_report_issue66.json`
- 결과: `total=28, pass=28, fail=0`

## 6) 문서 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - `커버리지 배치 v2 적용 절차` 섹션 추가
- `README.md`
  - v2 배치 실행 예시 추가

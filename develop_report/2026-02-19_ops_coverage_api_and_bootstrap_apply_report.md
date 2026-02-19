# 2026-02-19 Ops Coverage API And Bootstrap Apply Report

## 1) 이슈
- 대상: `#52 [DEVELOP] 커버리지 부트스트랩 적용 + 운영 커버리지 지표 API 추가`
- Report-Path: `develop_report/2026-02-19_ops_coverage_api_and_bootstrap_apply_report.md`

## 2) 목표
- `data/bootstrap_ingest_coverage_v1.json` 입력을 실DB에 적용하고,
- 운영 확인용 API `GET /api/v1/ops/coverage/summary`를 제공하며,
- runbook/README에 운영 확인 절차를 반영한다.

## 3) 구현 내용
1. 운영 커버리지 API 추가
- 파일: `app/api/routes.py`
- 엔드포인트: `GET /api/v1/ops/coverage/summary`
- 응답 필드:
  - `regions_covered`
  - `sido_covered`
  - `observations_total`
  - `latest_survey_end_date`
  - `generated_at`

2. 스키마/저장소 로직 추가
- 파일: `app/models/schemas.py`
  - `OpsCoverageSummaryOut` 추가
- 파일: `app/services/repository.py`
  - `fetch_ops_coverage_summary()` 추가
  - `poll_observations` + `regions` 기준 집계 쿼리 구현

3. 계약 검증 반영
- 파일: `tests/test_api_routes.py`
  - 커버리지 API 계약 테스트 추가
- 파일: `scripts/qa/run_api_contract_suite.sh`
  - 커버리지 API success/empty 케이스 추가
  - 스위트 설명을 `12-endpoint`로 갱신

4. 운영 문서 반영
- 파일: `README.md`
  - 공개 API 개수를 12개로 갱신
  - 커버리지 API 포함
  - 계약 스위트 설명을 12종으로 갱신
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 내부 운영 API 목록에 커버리지 API 추가
  - 운영 지표 확인 절차에 커버리지 확인 항목 추가

## 4) 실DB 적용 결과
1. 입력 파일
- `data/bootstrap_ingest_coverage_v1.json` (100 records)

2. 적용 실행
- 실행: `python -m app.jobs.bootstrap_ingest --input data/bootstrap_ingest_coverage_v1.json --report data/bootstrap_ingest_coverage_v1_apply_report.json`
- 원격 DB 왕복 시간이 길어 실행 안정성 확보를 위해 1건 단위 루프로 동일 적재 로직(`ingest_payload`)을 적용해 최종 리포트 생성

3. 적용 리포트
- 파일: `data/bootstrap_ingest_coverage_v1_apply_report.json`
- 요약:
  - `total=100`
  - `success=100`
  - `fail=0`
  - `review_queue_count=0`

## 5) 커버리지 API 실응답 확인
1. 호출 결과 저장
- 파일: `data/ops_coverage_summary_issue52.json`

2. 확인값
- `regions_covered=11`
- `sido_covered=6`
- `observations_total=102`
- `latest_survey_end_date=2026-02-18`

## 6) 계약/테스트 검증
1. API 단위 테스트
- `.venv/bin/pytest -q tests/test_api_routes.py tests/test_bootstrap_ingest.py`
- 결과: `5 passed`

2. 계약 스위트
- `bash scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue52.json`
- 결과: `total=27, pass=27, fail=0`
- 리포트: `data/qa_api_contract_report_issue52.json`

## 7) DoD 대응
1. 실DB 적용 결과 리포트 제출
- 충족 (`data/bootstrap_ingest_coverage_v1_apply_report.json`)

2. 커버리지 API 구현 + 계약 검증
- 충족 (`/api/v1/ops/coverage/summary`, `data/qa_api_contract_report_issue52.json`)

3. develop_report 제출
- 충족 (본 문서)

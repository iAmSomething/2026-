# 2026-02-19 Ops Coverage Contract Extension Report

## 1) 이슈
- 대상: `#62 [DEVELOP] ops/coverage/summary 계약 확장(state/warning/total)`
- Report-Path: `develop_report/2026-02-19_ops_coverage_contract_extension_report.md`

## 2) 목표
- `GET /api/v1/ops/coverage/summary` 계약을 UI/QA 검증 가능 수준으로 확장 고정
- `ready|partial|empty` 상태 규칙과 경고 문구를 명시

## 3) 구현 내용
1. API 응답 필드 확장
- 파일: `app/models/schemas.py`
- `OpsCoverageSummaryOut`에 아래 필드 추가
  - `state` (`ready|partial|empty`)
  - `warning_message`
  - `regions_total`
- 기존 필드 유지
  - `regions_covered`, `sido_covered`, `observations_total`, `latest_survey_end_date`

2. 상태 계산 로직 구현
- 파일: `app/services/repository.py`
- `fetch_ops_coverage_summary()` 확장
  - `regions_total`: `regions` 테이블 총 행 수
  - `regions_covered`: `poll_observations.region_code` distinct
  - `sido_covered`: 관측된 `sido_name` distinct
  - `observations_total`, `latest_survey_end_date` 집계
- 상태 규칙
  - `empty`: `observations_total == 0`
  - `partial`: 관측은 있으나 `regions_covered < regions_total` 또는 기준(`regions_total`) 미확보
  - `ready`: `regions_total > 0` and `regions_covered >= regions_total`

3. 라우트 반영
- 파일: `app/api/routes.py`
- `/api/v1/ops/coverage/summary`에서 확장 필드 반환

4. 계약 테스트 확장
- 파일: `tests/test_api_routes.py`
  - `ready/partial/empty` 3케이스 상태 계약 검증 추가
- 파일: `scripts/qa/run_api_contract_suite.sh`
  - coverage success 검증 필드 확장
  - coverage partial 케이스 추가
  - coverage empty 케이스에 state 검증 추가

5. 운영 문서 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - coverage API 확인 항목에 `state`, `warning_message`, `regions_total` 추가
  - 상태 해석 규칙 명시
- 파일: `README.md`
  - coverage API 주요 필드(`state`, `warning_message`, `regions_total`) 명시

## 4) 검증 결과
1. 단위/계약 테스트
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py`
- 결과: `6 passed`

2. 계약 스위트
- `bash scripts/qa/run_api_contract_suite.sh --report /tmp/qa_api_contract_report_issue62.json`
- 결과: `total=28, pass=28, fail=0`

## 5) API 실응답 샘플 3종
- 파일: `data/ops_coverage_summary_contract_samples.json`
- 포함:
  - `ready` 실응답(실DB 기반)
  - `partial` 실응답 샘플
  - `empty` 실응답 샘플

## 6) #50 필드 정합성
- #50에서 사용 요청한 필드명과 현재 계약 필드명 불일치 0건
  - `state`, `warning_message`, `regions_total`, `regions_covered`, `sido_covered`, `observations_total`, `latest_survey_end_date`

## 7) DoD 대응
1. API 실응답 샘플 JSON 3종 제출
- 충족 (`data/ops_coverage_summary_contract_samples.json`)
2. 계약 테스트 PASS
- 충족 (`total=28, pass=28, fail=0`)
3. 보고서 제출
- 충족 (본 문서)
4. #50 UI fallback 경로와 필드명 불일치 0건
- 충족

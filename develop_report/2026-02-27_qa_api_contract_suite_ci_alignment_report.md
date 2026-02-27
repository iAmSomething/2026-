# 2026-02-27 QA API Contract Suite CI Alignment Report

## 1) Scope
- Issue: #490
- Goal: Align CI/local case count and recover `QA API Contract Suite` to reliable green gate.

## 2) Root Cause
CI fail(5건) 원인은 스위트 자체 `FakeRepo` 계약이 최신 API 시그니처/스키마와 불일치한 것이었다.
- `search_regions(query, limit)` -> 실제 라우트는 `has_data` 인자 전달
- `fetch_region_elections(region_code)` -> 실제 라우트는 `topology`, `version_id` 전달
- matchup option 스키마에서 `candidate_id`가 필수인데 fixture 누락

## 3) Fixes
- `scripts/qa/run_api_contract_suite.sh` 업데이트:
  - FakeRepo 메서드 시그니처 최신화
    - `search_regions(..., has_data=None)`
    - `fetch_region_elections(..., topology="official", version_id=None)`
  - matchup fixture options에 `candidate_id` 추가
  - 케이스수 단일 소스 고정:
    - `expected_total = QA_API_CONTRACT_EXPECTED_TOTAL`(기본 31)
    - 불일치 시 `suite_case_count_alignment` fail case를 자동 추가

## 4) Verification
로컬 3회 연속 실행:
1. `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue490_run1.json`
2. `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue490_run2.json`
3. `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue490_run3.json`

결과(3회 동일):
- `summary: total=31, pass=31, fail=0`

## 5) Acceptance Mapping
- [x] CI/로컬 케이스수 기준(31) 단일화
- [x] 실패 5건 원인 분류/수정 반영
- [x] 스위트 green 재현(로컬 3회 연속 PASS)

## 6) Notes
- 본 수정은 QA 스위트 fixture/계약 동기화 변경이며, API 비즈니스 로직 변경은 없다.

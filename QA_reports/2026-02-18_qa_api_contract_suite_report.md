# QA API Contract Suite 구축 및 1차 실행 보고서

- Date: 2026-02-18
- Issue: #20
- Status: PASS
- Report-Path: `QA_reports/2026-02-18_qa_api_contract_suite_report.md`

## 1) 구현 내용
1. API 계약 스위트 스크립트 추가
- `scripts/qa/run_api_contract_suite.sh`

2. 수동 CI(workflow_dispatch) 연동
- `.github/workflows/qa-api-contract-suite.yml`

3. 결과 JSON 산출
- `data/qa_api_contract_report.json`

## 2) 검증 범위
- 대상 API 8종
  1. `GET /api/v1/dashboard/summary`
  2. `GET /api/v1/dashboard/map-latest`
  3. `GET /api/v1/dashboard/big-matches`
  4. `GET /api/v1/regions/search`
  5. `GET /api/v1/regions/{region_code}/elections`
  6. `GET /api/v1/matchups/{matchup_id}`
  7. `GET /api/v1/candidates/{candidate_id}`
  8. `POST /api/v1/jobs/run-ingest`

- 케이스 카테고리
  - `success`
  - `empty`
  - `failure` (404/422/500)
  - `auth_failure` (401/403)

## 3) 로컬 실행 결과
- 실행 명령:
```bash
scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report.json
```
- 결과 요약:
  - total: 19
  - pass: 19
  - fail: 0
  - pass_rate: 100.0%

## 4) CI 연동 상태
- `workflow_dispatch` 실행 가능한 워크플로 파일 반영 완료
- Actions 실행 링크: 브랜치 반영 후 1회 실행 링크를 이슈 코멘트에 추가 예정

## 5) 판정
- [QA PASS] 로컬 계약 스위트 기준 통과
- 잔여: GitHub Actions 수동 1회 실행 링크 첨부

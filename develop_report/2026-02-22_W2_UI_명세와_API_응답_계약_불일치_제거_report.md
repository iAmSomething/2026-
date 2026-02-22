# 2026-02-22 W2 UI 명세와 API 응답 계약 불일치 제거 report

## 1. 요약
- 이슈: `#178 [DEVELOP][W2] 대시보드 summary/map/big-matches 계약 동기화`
- 목표: 대시보드 3개 API(`summary`, `map-latest`, `big-matches`)의 응답 계약을 동일한 provenance 규칙으로 정렬

## 2. 구현
1. `big-matches` 응답 모델 확장
- 파일: `app/models/schemas.py`
- `BigMatchPoint`에 아래 필드를 추가
  - `audience_region_code`
  - `source_priority`
  - `official_release_at`
  - `article_published_at`
  - `freshness_hours`
  - `is_official_confirmed`

2. `big-matches` 조회 쿼리 확장
- 파일: `app/services/repository.py`
- 파생 메타 계산용 원천 필드 노출
  - `audience_region_code`
  - `observation_updated_at`
  - `official_release_at`
  - `article_published_at`(articles join)

3. 라우트 파생 규칙 통일
- 파일: `app/api/routes.py`
- `get_dashboard_big_matches`에서 `_derive_source_meta(...)`를 적용해
  `summary/map-latest`와 동일 규칙으로 `source_priority`, `freshness_hours`, `is_official_confirmed`를 계산

4. 테스트/계약 스위트 동기화
- 파일: `tests/test_api_routes.py`
  - `big-matches` 계약 assertion에 신규 필드 검증 추가
- 파일: `scripts/qa/run_api_contract_suite.sh`
  - `big_matches_success` 케이스에 필수 키 검증 추가

5. 문서 반영
- 파일: `docs/03_UI_UX_SPEC.md`
  - `빅매치 카드` 필수 필드 목록에 provenance 필드 추가
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 일일 운영 체크에 `dashboard/big-matches` freshness/source_priority 확인 항목 추가
- 파일: `data/scope_segregation_dashboard_samples_v1.json`
  - `dashboard_big_matches` 샘플을 신규 계약에 맞춰 갱신

## 3. 검증
1. 단위/라우트 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_api_routes.py`
- 결과: `10 passed`

2. API 계약 스위트
- 명령: `bash scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue178.json`
- 결과: `total=28, pass=28, fail=0`

3. 샘플 응답 확인
- `big-matches` 샘플에서 신규 필드 존재 확인:
  - `source_priority`
  - `official_release_at`
  - `article_published_at`
  - `freshness_hours`
  - `is_official_confirmed`

## 4. 증빙 파일
- `data/qa_api_contract_report_issue178.json`
- `data/verification/issue178_dashboard_contract_pytest.log`
- `data/verification/issue178_dashboard_contract_suite.log`
- `data/verification/issue178_big_matches_contract_sample.json`

## 5. DoD 체크
- [x] 구현/설계/검증 반영
- [x] 보고서 제출
- [x] 이슈 코멘트에 report_path/evidence/next_status 기재 예정

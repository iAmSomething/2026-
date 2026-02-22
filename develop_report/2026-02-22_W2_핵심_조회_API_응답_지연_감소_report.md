# 2026-02-22 W2 핵심 조회 API 응답 지연 감소 report

## 1. 요약
- 이슈: `#179 [DEVELOP][W2] candidates/matchups 조회 성능 튜닝 1차`
- 목표: 후보/매치업 조회 경로에서 응답 지연 원인을 줄이는 1차 튜닝 반영

## 2. 구현
1. `matchups/{matchup_id}` 조회 쿼리 왕복 감소
- 파일: `app/services/repository.py`
- 변경 전: `poll_observations` 조회 1회 + `poll_options` 조회 1회(총 2회)
- 변경 후: `LEFT JOIN LATERAL + json_agg`로 옵션을 동일 쿼리에서 집계(총 1회)
- 효과: 매치업 상세 조회의 DB 왕복 비용 감소

2. 읽기 경로 인덱스 추가
- 파일: `db/schema.sql`
- 추가 인덱스
  - `idx_poll_observations_matchup_latest` on `(matchup_id, survey_end_date DESC, id DESC)`
  - `idx_poll_options_observation_value` on `(observation_id, value_mid DESC, option_name)`
  - `idx_review_queue_entity_status` on `(entity_type, entity_id, status)`
- 목적
  - 최신 매치업 1건 선택 정렬 비용 절감
  - 옵션 정렬 조회 비용 절감
  - `matchup/candidate`의 `review_queue EXISTS` 탐색 비용 절감

3. 회귀 방지 테스트 보강
- 파일: `tests/test_repository_matchup_legal_metadata.py`
  - `get_matchup`에서 옵션 포함 row를 단일 조회로 처리하는 경로 검증
  - `execute` 호출 횟수 `1`회 assertion 추가
- 파일: `tests/test_schema_read_performance_indexes.py` (신규)
  - 신규 인덱스 정의 존재 여부 검증

## 3. 검증
1. 기능/회귀 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_repository_matchup_legal_metadata.py tests/test_schema_read_performance_indexes.py tests/test_api_routes.py`
- 결과: `12 passed`

2. API 계약 회귀 확인
- 명령: `bash scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue179.json`
- 결과: `total=28, pass=28, fail=0`

## 4. 증빙 파일
- `data/verification/issue179_full_pytest.log`
- `data/verification/issue179_read_perf_pytest.log`
- `data/verification/issue179_api_contract_suite.log`
- `data/verification/issue179_read_perf_summary.json`
- `data/verification/issue179_api_contract_report.json`
- `data/verification/issue179_api_contract_report_digest.json`

## 5. DoD 체크
- [x] 구현/설계/검증 반영
- [x] 보고서 제출
- [x] 이슈 코멘트에 report_path/evidence/next_status 기재 예정

# 2026-02-26 Issue #293 Candidate Verify Gate v1 Report

## 1. 대상 이슈
- Issue: #293 `[COLLECTOR][P0] 후보명 검증 게이트 v1(Data.go 후보자 매칭)`
- URL: https://github.com/iAmSomething/2026-/issues/293

## 2. 구현 요약
- 후보명 추출 1차 필터 강화:
  - `오차는`, `응답률은`, `지지율은` 등 비후보 토큰을 후보 추출 단계에서 제외.
- 후보 검증 2차 게이트 추가:
  - ingest 시 `option_type in (candidate, candidate_matchup)`만 검증.
  - Data.go 후보자 API 매칭 성공 시 `candidate_verified=true`, `candidate_verify_source=data_go` 저장.
  - Data.go 미매칭이지만 기사 후보 목록(`record.candidates`) 매칭 시 `candidate_verify_source=article_context`로 통과.
- 미검증 후보 라우팅:
  - 노이즈 토큰/미검증 후보는 `candidate_verified=false`, `needs_manual_review=true`.
  - `review_queue(issue_type=mapping_error)`로 자동 라우팅.
- 저장/조회 계약 반영:
  - `poll_options`에 `candidate_verified`, `candidate_verify_source`, `candidate_verify_confidence` 컬럼 추가.
  - 후보 랭킹/매치업 조회에서 `candidate_verified=false` 옵션 기본 제외.

## 3. 변경 파일
- 코드
  - `src/pipeline/collector.py`
  - `app/services/ingest_service.py`
  - `app/services/data_go_candidate.py`
  - `app/services/ingest_input_normalization.py`
  - `app/services/repository.py`
  - `app/models/schemas.py`
  - `db/schema.sql`
- 테스트
  - `tests/test_collector_extract.py`
  - `tests/test_ingest_service.py`
  - `tests/test_normalize_ingest_payload_for_schedule.py`
  - `tests/test_schema_party_inference.py`
  - `tests/test_bootstrap_ingest.py`

## 4. 검증 결과
- 실행:
  - `../election2026_codex/.venv/bin/pytest -q tests/test_ingest_service.py tests/test_collector_extract.py tests/test_schema_party_inference.py tests/test_normalize_ingest_payload_for_schedule.py`
  - `../election2026_codex/.venv/bin/pytest -q`
- 결과:
  - `30 passed`
  - `173 passed`

## 5. 수용 기준 대비
1. 비후보 토큰이 matchup 옵션에 0건
- 충족: 추출기 stopword 강화 + `tests/test_collector_extract.py`에서 `응답률은` 제외 검증.

2. 비정상 옵션(`오차는`, `응답률은`) 재현 시 review_queue 이동
- 충족: `tests/test_ingest_service.py`에서 `CANDIDATE_TOKEN_NOISE`가 `mapping_error`로 라우팅됨을 검증.

3. 검증 실패 후보 기본 랭킹 제외
- 충족: `app/services/repository.py` 조회 SQL에 `COALESCE(po.candidate_verified, TRUE) = TRUE` 필터 반영.

## 6. 의사결정 필요사항
1. `candidate_verify_confidence` 기준선 확정 필요
- 현재 기본값: `data_go(0.82~0.98)`, `article_context(0.68)`, `manual(0.0/0.2)`.
- QA/운영에서 사용할 통과 컷(예: 0.7/0.8) 확정이 필요합니다.

2. 비후보 옵션(`party_support`, `election_frame` 등)의 `candidate_verify_source` 표준값 확정 필요
- 현재는 비후보 옵션을 `candidate_verified=true`, `candidate_verify_source=manual`로 저장합니다.
- 비후보는 `NULL`로 둘지(의미 분리), 현재처럼 `manual`로 고정할지 정책 확정이 필요합니다.

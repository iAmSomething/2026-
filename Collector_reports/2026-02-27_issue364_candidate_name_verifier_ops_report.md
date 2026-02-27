# 2026-02-27 Issue #364 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#364` `[W3][COLLECTOR][P2] 후보자명 검증기(data.go.kr + 웹 신호) 운영 적용`
- 목표:
  - 잡음 토큰(비인명) 후보 노출 차단
  - 후보 검증 근거 필드(`source`, `score`, `matched_key`) 저장
  - 저신뢰/잡음 후보의 review_queue 분기 보장

## 2) 반영 내용
- 신규 공통 정책 모듈 추가
  - `app/services/candidate_token_policy.py`
  - 조사 결합형(예: `국민의힘은`) 및 지역어근(예: `전라는`) 포함 노이즈 토큰 판별
- ingest 경로 보강
  - `app/services/ingest_service.py`
  - `candidate_verify_matched_key` 계산/저장 추가
  - `data_go`/`article_context`/`manual` 결과별 matched_key 부여
  - 잡음 토큰은 `CANDIDATE_TOKEN_NOISE`로 manual review 라우팅
- 저장소/조회 경로 보강
  - `app/services/repository.py`
  - `poll_options` 저장 컬럼 `candidate_verify_matched_key` 반영
  - 조회 시 `candidate_verify_source/confidence` null fallback 보정
- map-latest 노이즈 필터 보강
  - `app/api/routes.py`
  - 공통 후보 토큰 정책으로 map-latest noise 판정 일원화
- 스키마 반영
  - `db/schema.sql`
  - `poll_options.candidate_verify_matched_key TEXT NULL` 추가
- 입력 정규화/스키마
  - `app/services/ingest_input_normalization.py`
  - `app/models/schemas.py`

## 3) 테스트 반영
- `tests/test_ingest_service.py`
  - 조사 결합형 노이즈 토큰(`국민의힘은`) 차단 및 review_queue 분기 테스트 추가
  - `data_go` 검증 시 matched_key(`data_go:cand-jwo`) 검증 추가
- `tests/test_repository_matchup_scenarios.py`
  - `더불어민주당은/국민의힘은/전라는` 노이즈 필터 테스트 반영
- `tests/test_map_latest_cleanup_policy.py`
  - map-latest에서 `국민의힘은` exclusion reason 검증 추가
- `tests/test_normalize_ingest_payload_for_schedule.py`
  - `candidate_verify_matched_key` 정규화 테스트 추가
- `tests/test_schema_party_inference.py`
  - schema 컬럼 추가 검증 반영

## 4) 검증 결과
- 실행 명령:
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py tests/test_repository_matchup_scenarios.py tests/test_map_latest_cleanup_policy.py tests/test_schema_party_inference.py tests/test_normalize_ingest_payload_for_schedule.py -q`
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_api_routes.py -q`
- 결과:
  - `28 passed`
  - `29 passed`

## 5) 증적 파일
- `data/issue364_candidate_verifier_after_evidence.json`

핵심 확인값:
- hotspot 토큰 판정: `더불어민주당은/국민의힘은/전라는` 모두 `is_noise_candidate_token=true`
- low-confidence/review_queue 분기 샘플:
  - `candidate verification manual review required: 국민의힘은:CANDIDATE_TOKEN_NOISE`
- source/score/matched_key 샘플 2건:
  - `정원오`: `data_go / 0.97 / data_go:cand-jwo`
  - `오세훈`: `article_context / 0.68 / article_context:cand-oh`

## 6) 수용기준 대응
1. invalid token 노출 0
- 문제 토큰 유형(정당명+조사, 지역어근) 노이즈 정책에 포함하여 ingest/repository/map-latest 모두에서 차단.

2. `candidate_verified` 근거 필드 채움
- `candidate_verify_source`, `candidate_verify_confidence`, `candidate_verify_matched_key` 저장 로직 반영.

3. QA 교차검증 PASS 가능 상태 확보
- #376 blocker 요청 항목(토큰 차단, review_queue 샘플, 근거 필드 샘플) 증빙 파일로 제출 가능 상태.

## 7) 의사결정 요청
1. `candidate_verify_matched_key`를 API 응답(`GET /api/v1/matchups/{id}`) 기본 필드로 고정 노출할지 결정이 필요합니다.
2. 지역어근(`전라/경상/충청`) 노이즈 판정은 현재 하드코딩입니다. 운영에서 화이트리스트 예외(동명이인/신규 후보명)를 둘지 정책 확정이 필요합니다.

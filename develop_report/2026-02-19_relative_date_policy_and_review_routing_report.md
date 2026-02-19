# 2026-02-19 Relative Date Policy and Review Routing Report (Issue #91)

## 1. 작업 개요
- 이슈: [#91](https://github.com/iAmSomething/2026-/issues/91)
- 목표: 상대시점 변환 정책화 + 불확실성/실패 review_queue 라우팅 + 정책 카운트 운영 추적
- 브랜치: `codex/issue91-relative-date-policy`

## 2. 구현 내용
### 2.1 변환 정책 플래그 도입
- 파일: `src/pipeline/collector.py`
- 정책:
  - `strict_fail` (기본)
  - `allow_estimated_timestamp`
- 동작:
  - 상대시점 문구(어제/그제/오늘/지난주/최근) 감지
  - `published_at` 기준 변환 우선
  - `published_at` 결측 시
    - `strict_fail`: `date_inference_mode=strict_fail_blocked`, `survey_end_date=null`, review_queue 라우팅
    - `allow_estimated_timestamp`: `collected_at` fallback 추정, `date_inference_mode=estimated_timestamp`, review_queue 라우팅

### 2.2 데이터 모델 확장
- 파일: `db/schema.sql`
  - `poll_observations` 신규 컬럼:
    - `date_inference_mode`
    - `date_inference_confidence`
  - `ingestion_runs` 신규 컬럼:
    - `date_inference_failed_count`
    - `date_inference_estimated_count`
- 파일: `app/models/schemas.py`
  - `PollObservationInput`, `MatchupOut`에 `date_inference_mode`, `date_inference_confidence` 반영
- 파일: `src/pipeline/contracts.py`, `src/pipeline/ingest_adapter.py`
  - collector->ingest 계약에 inference 필드 반영

### 2.3 운영 라우팅 + 카운트
- 파일: `src/pipeline/collector.py`
  - 불확실/실패 건 자동 review_queue 라우팅 (`extract_error` + 세부 error_code)
    - `RELATIVE_DATE_UNCERTAIN`
    - `RELATIVE_DATE_ESTIMATED`
    - `RELATIVE_DATE_STRICT_FAIL`
- 파일: `app/services/ingest_service.py`
  - `date_inference_mode/confidence` 기준으로 불확실 건 review_queue 라우팅
  - 실행 종료 시 정책 카운트 저장
- 파일: `app/services/repository.py`
  - `update_ingestion_policy_counters(...)` 추가
  - `fetch_ops_ingestion_metrics`에 정책 카운트 집계 포함

### 2.4 API/문서/샘플
- 파일: `app/services/repository.py`
  - `GET /api/v1/matchups/{matchup_id}` 응답에 inference 필드 노출
- 파일: `docs/01_DATA_PIPELINE_STRATEGY.md`
  - 상대시점 정책 섹션 추가
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - `date_inference_*` 필드/정책 반영
- 파일: `docs/03_UI_UX_SPEC.md`
  - matchup 상세 필수 필드에 inference 항목 반영
- 파일: `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
  - 선택 환경변수 `RELATIVE_DATE_POLICY` 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 운영 규칙/지표 항목 업데이트
- 샘플/비교:
  - `data/legal_metadata_matchup_sample_v1.json`
  - `data/relative_date_policy_comparison_v1.json`

## 3. 테스트/검증
### 3.1 정책/라우팅 테스트
- `tests/test_collector_extract.py`
  - strict_fail 라우팅
  - allow_estimated_timestamp fallback
  - 저신뢰(`confidence < 0.8`) 라우팅
- `tests/test_ingest_service.py`
  - 불확실 inference review_queue 라우팅 + ingestion_runs 정책 카운트 업데이트 검증

### 3.2 계약/저장 테스트
- `tests/test_schema_legal_metadata.py`
  - 스키마/마이그레이션 구문 검증
- `tests/test_repository_matchup_legal_metadata.py`
  - matchup 조회 필드 검증
- `tests/test_api_routes.py`, `tests/test_ingest_adapter.py`, `tests/test_poll_fingerprint.py`
  - 계약/전파/병합 회귀 검증

### 3.3 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_collector_extract.py tests/test_ingest_service.py tests/test_repository_matchup_legal_metadata.py tests/test_schema_legal_metadata.py tests/test_api_routes.py tests/test_ingest_adapter.py tests/test_poll_fingerprint.py`
  - 결과: `28 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
  - 결과: `67 passed`

## 4. DoD 충족 여부
1. 정책 플래그 + 저장 필드 + 라우팅 테스트 PASS: 완료
2. 정책별 결과 비교 샘플 제출: 완료 (`data/relative_date_policy_comparison_v1.json`)
3. 운영 문서 업데이트: 완료 (`docs/05_RUNBOOK_AND_OPERATIONS.md` 포함)

# 2026-02-19 Party Inference Schema/API Report

## 1. 작업 목표
- Issue: #101 `[DEVELOP] 정당 추정 결과 스키마/API/검수 연계 확장`
- 범위:
  1. 저장 계층: party inference 필드 추가
  2. API 확장: matchup 상세 옵션 응답에 추정 필드 노출
  3. 검수 연계: low confidence 자동 review_queue 라우팅

## 2. 구현 내용
1. DB 스키마 확장 (`db/schema.sql`)
- `poll_options` 컬럼 추가
  - `party_inferred BOOLEAN NOT NULL DEFAULT FALSE`
  - `party_inference_source TEXT NULL`
  - `party_inference_confidence FLOAT NULL`
- 기존 DB 호환용 `ALTER TABLE poll_options ADD COLUMN IF NOT EXISTS ...` 추가

2. 모델/계약 확장 (`app/models/schemas.py`)
- `PollOptionInput`에 신규 3필드 추가
- `MatchupOptionOut`에 신규 3필드 추가

3. Repository 반영 (`app/services/repository.py`)
- `upsert_poll_option` insert/upsert 대상에 신규 3필드 포함
- `get_matchup` 옵션 조회에 신규 3필드 포함

4. Ingest 검수 라우팅 반영 (`app/services/ingest_service.py`)
- 임계값: `PARTY_INFERENCE_REVIEW_THRESHOLD = 0.8`
- 조건:
  - `party_inferred=true`
  - `party_inference_confidence < 0.8`
- 액션:
  - `review_queue`에 `issue_type='party_inference_low_confidence'`로 적재

5. 문서 동기화
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - `poll_options` 주요 컬럼/정책에 party inference 반영
- `docs/03_UI_UX_SPEC.md`
  - `GET /api/v1/matchups/{matchup_id}` 필수 필드에 party inference 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - low confidence 정당 추론 검수 라우팅 규칙 추가

6. 샘플 응답
- `data/party_inference_matchup_sample_v1.json` 추가

## 3. 테스트
1. migration/repository/API/ingest 타깃 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_schema_party_inference.py tests/test_repository_matchup_legal_metadata.py tests/test_api_routes.py tests/test_ingest_service.py`
- 결과: `13 passed`

2. 전체 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `69 passed`

## 4. DoD 점검
1. migration + repository + API contract 테스트 PASS: 완료
2. 샘플 응답 + 운영 문서 업데이트: 완료
3. 보고서 제출: 완료

## 5. 산출물
- `develop_report/2026-02-19_party_inference_schema_api_report.md`
- `data/party_inference_matchup_sample_v1.json`

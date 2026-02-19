# 2026-02-19 Legal Metadata Schema/API Extension Report (Issue #86)

## 1. 작업 개요
- 이슈: [#86](https://github.com/iAmSomething/2026-/issues/86)
- 목표: 기사 법정메타 v2 수집 결과를 저장/조회 가능한 스키마/API 계약으로 확장
- 브랜치: `codex/issue86-legal-metadata-extension`

## 2. 구현 내용
### 2.1 저장 계층 확장
- 파일: `db/schema.sql`
- `poll_observations` 확장:
  - `confidence_level FLOAT NULL` 추가
  - 기존 법정메타 필드(`survey_start_date`, `survey_end_date`, `margin_of_error`, `response_rate`, `sample_size`, `audience_scope`, `audience_region_code`)와 함께 v2 저장 범위 정렬
- 마이그레이션 호환:
  - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS confidence_level FLOAT NULL`

### 2.2 API 계약 확장
- 파일: `app/models/schemas.py`
- `MatchupOut`에 법정메타 필드 명시 노출:
  - `survey_start_date`, `survey_end_date`
  - `confidence_level`, `margin_of_error`
  - `response_rate`, `sample_size`
  - `audience_scope`, `audience_region_code`
- `PollObservationInput`에도 `confidence_level` 입력 필드 추가

- 파일: `app/services/repository.py`
  - upsert/조회 쿼리에 `confidence_level` 반영
  - `get_matchup` 응답 딕셔너리에 법정메타 필드 일관 노출

- 파일: `app/services/fingerprint.py`
  - 병합 메타 필드에 `confidence_level` 포함

### 2.3 문서 동기화
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - `confidence_level` 포함 및 법정메타 null/결측 정책 명시
- 파일: `docs/03_UI_UX_SPEC.md`
  - `GET /api/v1/matchups/{matchup_id}` 필수 필드 목록에 법정메타 확장 반영

### 2.4 샘플 응답
- 파일: `data/legal_metadata_matchup_sample_v1.json`
- 매치업 상세 법정메타 필드 전체 포함 예시 1세트 제공

## 3. 테스트/검증
### 3.1 추가/수정 테스트
- 신규: `tests/test_schema_legal_metadata.py`
  - schema에 legal metadata/migration 구문 존재 검증
- 신규: `tests/test_repository_matchup_legal_metadata.py`
  - repository `get_matchup` 반환 필드 검증
- 수정:
  - `tests/test_api_routes.py` (matchup 계약 검증 강화)
  - `tests/test_ingest_service.py` (ingest 저장 경로 검증)
  - `tests/test_poll_fingerprint.py` (병합 필드 반영)

### 3.2 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_schema_legal_metadata.py tests/test_repository_matchup_legal_metadata.py tests/test_api_routes.py tests/test_ingest_service.py tests/test_poll_fingerprint.py`
  - 결과: PASS
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
  - 결과: PASS

## 4. null/결측 정책
- 법정메타 필드 결측 시 DB는 `null` 저장
- API는 결측을 `null`로 그대로 노출
- 배열형 provenance 필드는 기존 정책대로 `[]` fallback 유지

## 5. DoD 충족 여부
1. 테스트 PASS: 완료
2. 문서 계약 동기화: 완료
3. 보고서 + 샘플 응답 제출: 완료

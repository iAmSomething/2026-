# 2026-02-19 Metadata Schema Scope Separation Report (Issue #70)

## 1. 작업 개요
- 이슈: [#70](https://github.com/iAmSomething/2026-/issues/70)
- 목표: 여론조사 메타데이터(스코프/법정 completeness) 저장-적재-조회 계약 확장 및 national 집계 오염 방지
- 작업 브랜치: `codex/issue70-metadata-scope-separation`

## 2. 구현 내용
### 2.1 DB 스키마 확장
- 파일: `db/schema.sql`
- 반영 컬럼(`poll_observations`):
  - `audience_scope` (`national|regional|local`)
  - `audience_region_code`
  - `sampling_population_text`
  - `legal_completeness_score`
  - `legal_filled_count`
  - `legal_required_count`
  - `date_resolution`
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 추가로 기존 DB에도 무중단 확장 가능하게 반영
- `audience_scope` check constraint 추가
- 집계 성능용 인덱스 추가: `idx_poll_observations_scope_date`

### 2.2 Ingest 매핑/저장 경로 반영
- 파일: `app/models/schemas.py`
  - `PollObservationInput`에 신규 메타 필드 추가
- 파일: `app/services/repository.py`
  - `upsert_poll_observation` INSERT/UPSERT 컬럼에 신규 필드 반영
  - payload 기본값 처리(`setdefault`)로 누락 입력 호환 유지
- 파일: `src/pipeline/ingest_adapter.py`
  - collector 산출물의 신규 메타 필드를 ingest payload observation에 매핑
- 파일: `src/pipeline/contracts.py`
  - poll observation contract schema/dataclass에 신규 필드 반영

### 2.3 API 응답 확장
- 파일: `app/models/schemas.py`
  - `MatchupOut`에 아래 필드 추가:
    - `audience_scope`, `audience_region_code`, `sampling_population_text`
    - `legal_completeness_score`, `legal_filled_count`, `legal_required_count`, `date_resolution`
- 파일: `app/services/repository.py`
  - `get_matchup` 조회/응답에 신규 필드 포함

### 2.4 대시보드 요약 스코프 분리
- 파일: `app/services/repository.py`
- `fetch_dashboard_summary`에 스코프 필터 적용:
  - `o.audience_scope = 'national' OR o.audience_scope IS NULL`
- CTE(`latest`)와 최종 SELECT 모두에 필터를 적용해 같은 날짜의 `regional/local` 데이터가 섞이는 경우도 차단

### 2.5 문서 동기화
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - 메타 필드/스코프 분리 집계 규칙 추가
- 파일: `docs/03_UI_UX_SPEC.md`
  - summary national-only 규칙, matchup completeness 필드 노출 규칙 반영

## 3. 테스트/검증
### 3.1 신규/수정 테스트
- `tests/test_repository_dashboard_summary_scope.py` (신규)
  - summary SQL에 스코프 필터가 CTE+최종 쿼리에 모두 적용되는지 검증
- `tests/test_api_routes.py`
  - matchup 응답의 scope/completeness 필드 노출 검증 추가
- `tests/test_ingest_service.py`
  - ingest idempotent 경로에서 신규 메타 필드 전달/보존 검증 추가
- `tests/test_ingest_adapter.py`
  - collector -> ingest 변환 시 신규 메타 필드 매핑 검증 추가

### 3.2 실행 결과
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_ingest_service.py tests/test_ingest_adapter.py tests/test_api_routes.py tests/test_repository_dashboard_summary_scope.py`
- 결과: `11 passed`

- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `55 passed`

## 4. DoD 충족 여부
1. 마이그레이션/스키마 반영 증빙: 완료 (`db/schema.sql` 확장 + 호환 ALTER)
2. API 계약 테스트 PASS: 완료 (`tests/test_api_routes.py`)
3. regional 데이터가 national 집계에 섞이지 않음 검증: 완료 (`tests/test_repository_dashboard_summary_scope.py`)
4. 보고서 제출: 완료 (본 문서)

## 5. 의사결정 필요사항
1. legacy null 스코프 처리 정책 확정 필요
- 현재 구현: `audience_scope IS NULL`을 national 집계에 임시 포함(기존 데이터 호환)
- 선택지:
  - A) 현행 유지(호환 우선)
  - B) null 완전 제외(오염 방지 우선)
- 오너가 선택하면 쿼리 정책 고정 및 문서 문구 최종 확정 가능

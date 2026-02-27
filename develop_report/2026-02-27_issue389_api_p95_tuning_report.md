# 2026-02-27 Issue #389 핵심 API 성능 튜닝(P95) 보고서

## 1. 작업 목표
- 대상: 핵심 조회 API(`dashboard/summary`, `dashboard/map-latest`, `dashboard/big-matches`, `matchups/{id}`)
- 목표: P95 지연 편차 완화
- 제약: 데이터 신선도 훼손 없이 적용

## 2. 적용한 개선

### 2.1 Read Path TTL 캐시(짧은 TTL)
- 파일: `app/services/repository.py`
- 신규 구성:
  - 모듈 전역 read cache (`_API_READ_CACHE`)
  - TTL 기반 get/set (`_api_read_cache_get`, `_api_read_cache_set`)
  - 캐시 키 표준화 (`_api_read_cache_key`)
  - 수동 초기화 유틸 (`clear_api_read_cache`)
- 캐시 적용 메서드:
  - `fetch_dashboard_summary`
  - `fetch_dashboard_map_latest`
  - `fetch_dashboard_big_matches`
  - `get_matchup`
- 운영 설정:
  - `API_READ_CACHE_TTL_SEC` (기본 `0`, 비활성)
  - 활성화 권장값: `15~30`초

### 2.2 쓰기 경로 캐시 무효화
- 파일: `app/services/repository.py`
- 데이터 변경 메서드 `commit` 직후 `self._invalidate_api_read_cache()` 적용
- 목적: 짧은 TTL 캐시 사용 시에도 쓰기 직후 stale 응답 노출 최소화

### 2.3 인덱스 튜닝
- 파일: `db/schema.sql`
- 추가 인덱스:
  - `idx_poll_observations_verified_date`
  - `idx_poll_observations_verified_region_office_date`
  - `idx_poll_options_summary_type_observation`
  - `idx_poll_options_candidate_matchup_observation_value`
- 기대 효과:
  - `verified=true` hot path 필터링 비용 감소
  - summary/map/matchup에서 option+observation join/정렬 비용 감소

### 2.4 환경 문서 반영
- 파일: `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- 추가:
  - `API_READ_CACHE_TTL_SEC` 설명 (기본 `0`, 권장 `15~30`)

## 3. 성능 근거(정량)

### 3.1 캐시 hit 시 DB 쿼리 감소
- 테스트: `tests/test_repository_read_cache.py`
- 결과:
  - 동일 summary 2회 호출
  - 캐시 비활성(TTL=0): SQL 2회
  - 캐시 활성(TTL=30): SQL 1회

### 3.2 신선도 안전장치
- 테스트: `tests/test_repository_read_cache.py::test_write_path_invalidates_dashboard_summary_cache`
- 결과:
  - 캐시 hit 후 write 발생 시 캐시 무효화
  - 다음 read에서 SQL 재실행(신규 데이터 반영 경로 확보)

## 4. 검증 실행
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_read_cache.py tests/test_schema_read_performance_indexes.py`
  - 결과: `4 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_dashboard_summary_scope.py tests/test_repository_matchup_legal_metadata.py tests/test_repository_matchup_scenarios.py tests/test_repository_region_elections_master.py`
  - 결과: `13 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py`
  - 결과: `31 passed`

## 5. 변경 파일
- `app/config.py`
- `app/services/repository.py`
- `db/schema.sql`
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- `tests/test_repository_read_cache.py`
- `tests/test_schema_read_performance_indexes.py`

## 6. 운영 적용 권장
1. `API_READ_CACHE_TTL_SEC=20`으로 먼저 적용
2. QA/스테이징에서 API P95 비교 후(캐시 off vs on) 운영 반영
3. 배치/수동 적재 직후 응답 신선도 체크(캐시 무효화 정상 동작 확인)

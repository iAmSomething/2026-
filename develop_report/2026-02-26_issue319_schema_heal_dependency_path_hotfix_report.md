# 2026-02-26 Issue #319 Schema Heal Dependency Path Hotfix Report

## 1) 배경
- 운영 재검증에서 `/health/db`는 `ok`로 복구됐지만, `/api/v1/regions/42-000/elections`는 계속 `503` + `42P01`.
- 원인 분석 결과, `get_repository()`가 `psycopg.Error`를 즉시 `HTTPException`으로 변환하여 schema auto-heal 경로가 실행되지 않음.

## 2) 수정 내용
1. dependency 경로에서 schema mismatch 처리 추가
- 파일: `/Users/gimtaehun/election2026_codex/app/api/dependencies.py`
- SQLSTATE `42P01`/`42703` 감지 시 `heal_schema_once()` 시도
- heal 성공 시: `503` + `database schema auto-healed; retry request`
- heal 미적용 시: `503` + `database schema mismatch detected`

2. 단위 테스트 추가
- 파일: `/Users/gimtaehun/election2026_codex/tests/test_api_dependencies.py`
- 검증 항목:
  - schema mismatch + heal success
  - schema mismatch + heal not applied
  - non-schema DB error 기본 동작 유지

## 3) 테스트
- 실행:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_dependencies.py tests/test_api_routes.py tests/test_runtime_db_guard.py`
- 결과:
  - `28 passed`

## 4) 기대 효과
- 스키마 미스매치 상황에서 첫 실패 요청 이후 heal 트리거가 실제로 실행됨.
- 재시도 시 `/api/v1/regions/{region_code}/elections` 경로의 42P01 잔존 가능성 감소.

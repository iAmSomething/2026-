# 2026-02-26 Issue #319 운영 API 500 핫픽스 보고서

## 1) 이슈
- 대상: https://2026-api-production.up.railway.app
- 재현(수집 시각: 2026-02-26)
  - `GET /health` -> `200`
  - `GET /api/v1/dashboard/summary` -> `500`
  - `GET /api/v1/dashboard/map-latest` -> `500`
  - `GET /api/v1/dashboard/big-matches` -> `500`
  - `GET /api/v1/regions/search?q=강원` -> `500`
  - `GET /api/v1/regions/42-000/elections` -> `500`
  - `GET /health/db` -> `404` (기존 미구현)

## 2) 원인 가설 정리
- 프로세스는 살아있으나 DB 의존 경로에서 실패하는 패턴.
- 가능성 2축:
  1. `DATABASE_URL` 미설정/오설정
  2. 런타임 DB 스키마가 코드 쿼리와 불일치(컬럼/테이블 누락)

## 3) 적용한 핫픽스
1. DB 의존성 에러를 500 대신 503으로 명확화
- 파일: `/Users/gimtaehun/election2026_codex/app/db.py`
- `DatabaseConfigurationError`, `DatabaseConnectionError` 추가
- 설정 누락/연결 실패를 명시적으로 분리

2. API 의존성 레이어에서 DB 에러 매핑 강화
- 파일: `/Users/gimtaehun/election2026_codex/app/api/dependencies.py`
- repository dependency에서 DB 설정/연결/쿼리 실패를 `503`으로 반환

3. 런타임 스키마 가드 추가
- 파일: `/Users/gimtaehun/election2026_codex/app/runtime_db_guard.py`
- Railway 환경(또는 `AUTO_APPLY_SCHEMA_ON_STARTUP=true`)에서 startup 시 `db/schema.sql` 자동 적용
- SQLSTATE `42P01`/`42703`(undefined table/column) 감지 시 1회 schema heal 시도

4. 운영 진단 엔드포인트 추가
- 파일: `/Users/gimtaehun/election2026_codex/app/main.py`
- `GET /health/db` 추가 (DB ping + bootstrap 상태)
- psycopg 예외 핸들러 추가 (스키마 mismatch 진단 메시지 제공)

## 4) 테스트
- 실행:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_runtime_db_guard.py`
- 결과:
  - `25 passed`

## 5) 운영 반영 후 검증 항목
- 아래 6개 endpoint가 모두 `200`인지 재확인 필요:
  1. `/api/v1/dashboard/summary`
  2. `/api/v1/dashboard/map-latest`
  3. `/api/v1/dashboard/big-matches`
  4. `/api/v1/regions/search?q=강원`
  5. `/api/v1/regions/42-000/elections`
  6. `/health/db`

## 6) 남은 확인/결정
- Railway 재배포 후에도 `DATABASE_URL` 오설정이면 `/health/db`가 `503(database_not_configured|database_connection_failed)`를 반환함.
- 이 경우 오너가 Railway 변수의 `DATABASE_URL` 실제값(특수문자 URL-encoding 포함)을 재확인해야 함.

# 2026-02-27 Issue #369 시계열 추세선 API v1 구현 보고서

## 1. 작업 개요
- 이슈: #369 `[W4][DEVELOP][P2] 시계열 추세선 API v1(/api/v1/trends/{metric}) 구현`
- 목표: 단면 지표 외에 시계열 추세 조회 API 제공

## 2. 구현 내용

### 2.1 API 계약 추가
- 파일: `app/api/routes.py`, `app/models/schemas.py`
- 신규 엔드포인트:
  - `GET /api/v1/trends/{metric}`
- Path 파라미터:
  - `metric`: `party_support | president_job_approval | election_frame`
- Query 파라미터:
  - `scope`: `national | regional | local` (기본 `national`)
  - `region_code`: optional (`scope=regional|local`일 때 필수)
  - `days`: `1..365` (기본 `30`)
- 응답 스키마:
  - `TrendsOut` (`metric`, `scope`, `region_code`, `days`, `generated_at`, `points`)
  - `TrendPoint` (`survey_end_date`, `option_name`, `value_mid`, `pollster`, `audience_scope`, `audience_region_code`, `source_trace`)

### 2.2 대표값 선택 trace 반영
- 동일 그룹 기준: `survey_end_date + option_name`
- 그룹 내 대표값 선택:
  - 기존 summary와 동일한 우선순위 로직(`_select_summary_representative`) 재사용
- trace 노출:
  - `source_trace.selected_source_tier`
  - `source_trace.selected_source_channel`

### 2.3 repository 쿼리 구현
- 파일: `app/services/repository.py`
- 신규 메서드:
  - `fetch_trends(metric, scope, region_code, days)`
- 정책:
  - `verified=true`만 조회
  - `survey_end_date` 기준 `days` 윈도우 필터
  - `scope` 필터 적용
  - `scope=regional|local` + `region_code` 조건 시 지역코드 필터 적용

### 2.4 문서 업데이트
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - 공개 API 목록에 trends 추가
  - trends 파라미터/필수조건/trace 규칙 명시
- 파일: `docs/03_UI_UX_SPEC.md`
  - UI 매핑 표에 추세선 카드 API 추가
  - regional/local에서 `region_code` 필수 규칙 명시

### 2.5 테스트 추가/보강
- 파일: `tests/test_api_routes.py`
  - trends 계약 검증
  - regional/local `region_code` 필수 검증
  - representative trace 검증
- 파일: `tests/test_repository_trends_query.py`
  - trends SQL 조건(scope/region/days) 검증

## 3. 검증 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_repository_trends_query.py`
- 결과: `36 passed`

## 4. 수용기준 대응
1. 30/90일 조회 PASS
- `days` 파라미터(`1..365`) 지원 및 30/90 호출 테스트 반영

2. 전국/지역 scope 분리 검증 PASS
- scope별 필터 적용, regional/local에서 `region_code` 강제

3. UIUX 연동 가능한 계약 확정
- `metric/scope/region_code/days/points/source_trace` 계약을 스키마+문서에 확정

## 5. 변경 파일
- `app/models/schemas.py`
- `app/services/repository.py`
- `app/api/routes.py`
- `tests/test_api_routes.py`
- `tests/test_repository_trends_query.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`

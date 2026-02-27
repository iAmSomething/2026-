# 2026-02-27 Issue #365 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#365` `[W4][COLLECTOR][P2] 기사/공식 출처 병합 대표값 선택기 trace 필드 강화`
- 목표:
  - 대표값 선택 기준(`source_priority + freshness + legal completeness`)을 쿼리/응답에 반영
  - `summary`와 `map-latest`에 선택 근거(trace) 동시 노출
  - 전국/지역 스코프 혼합을 map-latest 선택 단계에서 차단

## 2) 반영 내용
- 대표값 선택 로직 강화
  - `app/services/repository.py`
  - `fetch_dashboard_summary` 정렬식에 `source_priority score`, `legal_completeness_score`, `freshness anchor` 반영
  - `fetch_dashboard_map_latest`를 2단 랭킹으로 개편
    - 1차: `region_code+office_type+audience_scope` 내부 대표값 선별
    - 2차: `region_code+office_type` 단일 대표값 선택(`scope_rn=1`)
- trace 필드 스키마 확장
  - `app/models/schemas.py`
  - `SummaryPoint.selection_trace` 추가
  - `MapLatestPoint.selected_source_tier`, `selected_source_channel`, `selection_trace` 추가
- API 응답 trace 노출
  - `app/api/routes.py`
  - `_build_selection_trace(...)` 도입
  - `dashboard/summary`, `dashboard/map-latest` 응답에 `selection_trace` 주입
- 문서 업데이트
  - `docs/03_UI_UX_SPEC.md`: summary/map-latest 필드 목록에 trace 필드 반영
  - `docs/02_DATA_MODEL_AND_NORMALIZATION.md`: 대표값 선택 추적 필드 계약 추가

## 3) 테스트 반영
- 신규 테스트
  - `tests/test_repository_dashboard_map_latest_scope.py`
    - map-latest 쿼리의 scope 분리/우선순위 정렬 계약 검증
- 기존 테스트 보강
  - `tests/test_repository_dashboard_summary_scope.py`
    - legal completeness/source priority 정렬식 검증 추가
  - `tests/test_api_routes.py`
    - summary/map-latest `selection_trace` 필드 노출 검증 추가

## 4) 검증 결과
- 실행 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_repository_dashboard_summary_scope.py tests/test_repository_dashboard_map_latest_scope.py tests/test_map_latest_cleanup_policy.py tests/test_api_routes.py`
- 결과:
  - `36 passed`

## 5) 증적 파일
- `data/issue365_summary_map_trace_samples.json`
- `data/issue365_repository_query_contract_checks.json`

핵심 확인값:
- summary/map-latest 응답 모두 `selection_trace.algorithm_version=representative_v2`
- summary/map-latest 응답 모두 `selected_source_tier` 노출
- map-latest 쿼리 `PARTITION BY o.region_code, o.office_type, o.audience_scope` 적용
- map-latest 쿼리 `scoped_rank` + `scope_rn=1` 적용

## 6) 수용기준 대응
1. 요약 카드 중복 0
- map-latest 2단 랭킹(`scope_rn=1`)으로 region+office 단일 대표값 강제.

2. API 응답에 선택 근거 노출
- summary/map-latest에 `selected_source_tier`, `selected_source_channel`, `selection_trace` 추가.

3. QA 대표값 검증 PASS
- 관련 테스트 36건 통과.

## 7) 의사결정 요청
1. 대표값 선택 가중치에서 `legal_completeness_score`와 `freshness`의 우선순위를 현재 순서(legal 우선)로 고정할지 결정이 필요합니다.
2. `dashboard/big-matches`에도 동일한 `selection_trace` 필드를 즉시 확장할지(일관성 우선), 다음 이슈로 분리할지 결정이 필요합니다.

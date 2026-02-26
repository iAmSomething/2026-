# 2026-02-26 Issue #313 지역코드 Alias 정규화 v1 보고서

## 1) 작업 개요
- 이슈: [#313](https://github.com/iAmSomething/2026-/issues/313)
- 목표: `KR-xx/legacy` 형태 입력을 API 경계에서 canonical 지역코드로 정규화하고, 조회 결과를 일관되게 반환.

## 2) 구현 내용
1. 지역코드 정규화 모듈 추가
- 파일: `/Users/gimtaehun/election2026_codex/app/services/region_code_normalizer.py`
- 추가 함수: `normalize_region_code_input(raw_value)`
- 지원 입력 예시:
  - `KR-32`, `KR-42`, `32-000`, `32_000`, `42000`, `42-000`, `29-46-000`
- canonical 규칙:
  - legacy prefix 매핑 v1: `32 -> 42` (강원)
  - 그 외는 canonical 형식(`xx-xxx`, `xx-xx-xxx`)으로 정규화

2. API 경계 적용
- 파일: `/Users/gimtaehun/election2026_codex/app/api/routes.py`
- 반영 엔드포인트:
  - `GET /api/v1/regions/search`
    - 코드형 질의는 `search_regions_by_code`로 분기
  - `GET /api/v1/regions/{region_code}/elections`
    - path `region_code`를 canonical로 정규화 후 조회
  - `GET /api/v1/matchups/{matchup_id}`
    - `matchup_id`의 region segment를 canonical로 정규화

3. 관측성(로그)
- alias 입력이 canonical로 변환될 때 아래 이벤트 로그 추가:
  - `region_code_alias_normalized endpoint=regions.search ...`
  - `region_code_alias_normalized endpoint=regions.elections ...`
  - `region_code_alias_normalized endpoint=matchups.get ...`

4. Repository 확장
- 파일: `/Users/gimtaehun/election2026_codex/app/services/repository.py`
- 추가 메서드: `search_regions_by_code(region_code, limit)`
- 동작: `regions.region_code = %s` exact match 검색 + 기존 응답필드(`has_data`, `matchup_count`) 유지

## 3) 테스트
1. 신규 테스트
- `/Users/gimtaehun/election2026_codex/tests/test_region_code_normalizer.py`
- `/Users/gimtaehun/election2026_codex/tests/test_api_routes.py`
  - alias/canonical 결과 동일성
  - `/regions/{region_code}/elections` alias path 정규화
  - matchup id 내 alias region 정규화
- `/Users/gimtaehun/election2026_codex/tests/test_repository_region_search_hardening.py`
  - `search_regions_by_code` exact match SQL 및 빈 입력 가드

2. 실행 결과
- `pytest -q tests/test_api_routes.py tests/test_region_code_normalizer.py tests/test_repository_region_search_hardening.py`
- 결과: `33 passed in 1.37s`

## 4) 수용 기준 대비
- alias 입력 200 응답 + canonical 일관 반환: 충족
- canonical direct 입력과 결과 동일: 충족 (`/regions/search`)
- 강원 샘플 회귀(legacy `32 -> 42`): 충족

## 5) 리스크/후속 제안
- v1은 legacy prefix 매핑을 `32 -> 42`로 제한.
- 후속 의사결정 필요: legacy 코드 매핑 범위를 전국 단위로 확장할지 여부.

# 2026-02-26 Issue #368 regions/search 공식 선거구 기본 노출 전환 보고서

## 1) 이슈
- #368 `[W3][DEVELOP][P2] regions/search 기본동작을 공식 선거구 전체 노출로 전환`

## 2) 구현 요약
1. API 파라미터 확장
- `GET /api/v1/regions/search`
- `q/query`를 선택값으로 전환(빈 값 허용)
- `has_data` 선택 필터(`true|false`) 추가

2. 검색 기본 동작 전환
- `q/query`가 비어도 422를 반환하지 않고, 공식 선거구(활성 `elections`) 전체를 조회
- 기본 결과에 `has_data=false` 지역 포함

3. 리포지토리 쿼리 변경
- `search_regions` / `search_regions_by_code`에 `has_data` 필터 옵션 추가
- 조회 기준을 `regions + elections(official)`로 정렬/제한

4. 문서 갱신
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`

## 3) 테스트 및 증빙
- 실행:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q \
  tests/test_repository_region_search_hardening.py tests/test_api_routes.py
```
- 결과: `35 passed`

- 추가된 핵심 테스트
1. 빈 쿼리 기본 검색에서 공식 선거구+무데이터 노출 검증
2. `has_data=true` 필터 검증
3. 리포지토리 SQL의 공식 선거구 CTE/필터 파라미터 검증

- 샘플 캡처 파일
- `develop_report/assets/2026-02-26_issue368_regions_search_samples.json`
  - 세종(`29-000`), 강원(`42-000`) 무데이터 노출 사례 포함

## 4) 변경 파일
- `app/api/routes.py`
- `app/services/repository.py`
- `tests/test_api_routes.py`
- `tests/test_repository_region_search_hardening.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`
- `develop_report/assets/2026-02-26_issue368_regions_search_samples.json`
- `develop_report/2026-02-26_issue368_regions_search_official_exposure_report.md`

## 5) 수용기준 대응
1. 세종/강원 무데이터 선거구 검색 노출
- 기본 검색 응답에서 `29-000`, `42-000` + `has_data=false` 확인
2. UI 연동 회귀 없음
- API 경로/응답 필드 유지, 필터만 옵션 추가
3. QA PASS
- 관련 API/리포지토리 테스트 PASS (`35 passed`)

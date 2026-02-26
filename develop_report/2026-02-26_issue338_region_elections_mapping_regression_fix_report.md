# 2026-02-26 Issue338 Region Elections Mapping Regression Fix Report

## 1) 배경
- 운영 재현: `GET /api/v1/regions/29-000/elections`의 title이 세종이 아닌 광주 계열로 노출되는 회귀.
- 요구: region_code/title 정합성 보장 + 광역 코드 placeholder 슬롯 안정성 보강.

## 2) 수정 내용

### A. official topology 지역 라벨 보정
- 파일: `app/services/repository.py`
- 변경:
  - `fetch_region_elections()` 내부에 `apply_official_region_overrides()` 추가
  - `topology=official`일 때만 보정 적용
  - `29-000` 라벨을 `세종특별자치시`로 강제 보정
  - `XX-000` 코드의 admin_level/sigungu 기본값 보정(`sido`/`전체`)

### B. 광역 슬롯 생성 안정화
- 파일: `app/services/repository.py`
- 변경:
  - elections master가 비어있을 때 슬롯 결정 로직에서
    - `XX-000` 코드는 admin_level 값이 오염되어도 항상 광역 3슬롯
      (`광역자치단체장`, `광역의회`, `교육감`) 반환

## 3) 테스트

### 추가 테스트
- 파일: `tests/test_repository_region_elections_master.py`
- `test_region_elections_official_overrides_29_code_to_sejong_titles`
  - official에서 `29-000` 타이틀이 `세종시장/세종시의회/세종교육감`으로 보정되는지 검증
- `test_region_elections_returns_three_metro_slots_for_17_sido_codes_even_if_admin_level_corrupted`
  - 17개 `XX-000` 코드에서 admin_level 오염 상태여도 3슬롯 반환되는지 검증

### 실행 결과
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_repository_region_elections_master.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_api_routes.py tests/test_repository_region_elections_master.py`
- 결과:
  - `6 passed`
  - `30 passed`

## 4) 효과
- official topology 기준 `29-000` title 회귀 방지
- region master 비어있거나 admin_level이 비정상이어도 광역 3슬롯 안정 노출

## 5) 반영 파일
- `app/services/repository.py`
- `tests/test_repository_region_elections_master.py`

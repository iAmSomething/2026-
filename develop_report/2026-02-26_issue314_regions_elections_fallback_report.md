# 2026-02-26 Issue #314 regions/elections 서버 fallback 강제 반환 보고서

## 1) 작업 개요
- 이슈: [#314](https://github.com/iAmSomething/2026-/issues/314)
- 목표: `elections`(마스터) 테이블이 비어도 `/api/v1/regions/{region_code}/elections`에서 기본 선거 슬롯을 강제 반환.

## 2) 구현 내용
1. fallback 슬롯 규칙 수정 (핵심)
- 파일: `/Users/gimtaehun/election2026_codex/app/services/repository.py`
- 기존: 마스터가 비면 기본적으로 광역 3슬롯 + sigungu인 경우 기초 2슬롯 추가(총 5)
- 변경:
  - `admin_level = sido` -> `광역자치단체장`, `광역의회`, `교육감`
  - `admin_level = sigungu/local` -> `기초자치단체장`, `기초의회`
- 효과: 요구사항의 fallback 슬롯 개수(광역 3 / 기초 2)를 정확히 만족.

2. fallback 응답 필드 추가
- 파일: `/Users/gimtaehun/election2026_codex/app/models/schemas.py`
- `RegionElectionOut`에 필드 추가:
  - `is_fallback: bool`
  - `source: str`

3. source/is_fallback 계산 규칙
- 파일: `/Users/gimtaehun/election2026_codex/app/services/repository.py`
- `elections` 마스터 row 사용 시:
  - `is_fallback=false`
  - `source=elections.source` (없으면 `master`)
- 마스터 비어 생성된 row 시:
  - `is_fallback=true`
  - `source=generated`

## 3) 테스트
1. 수정/추가 테스트
- `/Users/gimtaehun/election2026_codex/tests/test_repository_region_elections_master.py`
  - sido fallback 3슬롯 + `is_fallback/source` 검증
  - sigungu fallback 2슬롯 검증
  - scenario fallback source/flag 검증
  - 마스터 row 존재 시 fallback 미사용 검증
- `/Users/gimtaehun/election2026_codex/tests/test_api_routes.py`
  - regions/elections 응답에 `is_fallback`, `source` 포함 검증

2. 실행 결과
- `pytest -q tests/test_api_routes.py tests/test_repository_region_elections_master.py tests/test_region_code_normalizer.py tests/test_repository_region_search_hardening.py`
- 결과: `37 passed in 5.92s`

## 4) 수용 기준 대응
- 42-000 조회 시 마스터 0건 환경 fallback 3슬롯 반환: 충족
- 26-710 조회 시 마스터 0건 환경 fallback 2슬롯 반환: 충족
- 마스터 데이터 존재 시 기존 결과 우선: 충족
- fallback 명시 필드(`is_fallback`, `source=generated`): 충족

## 5) 확인 필요(의사결정)
- `source`를 현재 `str`로 개방형 유지했음.
- 결정 필요: API 계약을 `Literal["master", "generated", "matchups"]`처럼 고정 enum으로 잠글지 여부.

# [DEVELOP] Issue #345 운영 API 데이터 품질 회귀 핫픽스 보고서

- 작성일: 2026-02-26
- 이슈: https://github.com/iAmSomething/2026-/issues/345
- 담당: role/develop
- 우선순위: P0

## 1) 배경
사용자 제보 기준으로 운영 화면에서 아래 품질 문제가 재현됨.

1. 지도/매치업에 비인명 토큰 노출(예: `재정자립도`, `지지`, `국정안정론` 등)
2. 후보 상세 카드 품질 저하 가능성(`name_ko` 공백/누락 방어 미흡)
3. 지역 검색 계약 정합 확인 필요

## 2) 원인 진단

### A. 매치업 옵션 정제 우회 버그
- 파일: `app/services/repository.py`
- 기존 `_is_noise_candidate_option()`에서 `candidate_id`가 있으면 즉시 통과 처리함.
- 결과: `cand:국정안정론` 같은 비정상 후보 ID/옵션이 노이즈 필터를 우회.

### B. map-latest 최종 방어 토큰 집합 부족
- 파일: `app/api/routes.py`
- 기존 generic 토큰 사전에 `재정자립도`, `지지` 계열이 포함되지 않아 일부 비인명 값이 통과 가능.

### C. 후보 상세 최소 표시값 방어 미흡
- 파일: `app/api/routes.py`
- `name_ko`가 공백/누락인 경우 fallback 처리 부재.

## 3) 적용 변경

### 3-1. 후보 옵션 노이즈 필터 강화
- 파일: `app/services/repository.py`
- `_CANDIDATE_NOISE_EXACT_TOKENS`/`_CANDIDATE_NOISE_SUBSTRING_TOKENS` 확장
  - 추가 예: `지지`, `지지도`, `재정자립도`, `적합도`, `선호도`, `국정안정론`, `국정견제론` 등
- `_is_noise_candidate_option()`에서 `candidate_id` 존재 시 우회하던 로직 제거
  - 이제 `candidate_id` 유무와 무관하게 토큰/패턴 기준으로 노이즈 차단

### 3-2. map-latest sanity 필터 강화
- 파일: `app/api/routes.py`
- `MAP_LATEST_GENERIC_OPTION_EXACT_TOKENS`/`MAP_LATEST_GENERIC_OPTION_SUBSTRINGS` 확장
  - `재정자립도`, `지지/지지도`, `적합도/선호도`, `국정안정론/국정견제론` 등 추가

### 3-3. 후보 상세 fallback 보강
- 파일: `app/api/routes.py`
- `GET /api/v1/candidates/{candidate_id}` 처리 시:
  - `name_ko`가 공백/누락이면 `candidate_id`로 fallback
  - `party_name`이 공백 문자열이면 `null` 정규화

## 4) 테스트/검증 결과

### 자동 테스트
- 실행:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest tests/test_api_routes.py tests/test_repository_matchup_scenarios.py -q`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest tests/test_repository_region_elections_master.py -q`
- 결과:
  - `27 passed` (`test_api_routes.py`, `test_repository_matchup_scenarios.py`)
  - `6 passed` (`test_repository_region_elections_master.py`)

### 신규/수정 테스트
- `tests/test_repository_matchup_scenarios.py`
  - `candidate_id`가 있어도 비인명 토큰(`국정안정론`, `재정자립도`)이 제거되는지 검증
- `tests/test_api_routes.py`
  - `map-latest`에서 `재정자립도`, `지지`가 `generic_option_token`으로 제외되는지 검증
  - 후보 상세 `name_ko` 누락 시 fallback 동작 검증

## 5) 영향도
- 목표 엔드포인트
  - `GET /api/v1/dashboard/map-latest`
  - `GET /api/v1/matchups/{matchup_id}` (옵션 정제 경로)
  - `GET /api/v1/candidates/{candidate_id}`
- 기대 효과
  - 후보명이 아닌 정책/지표 토큰 노출 감소
  - 사용자 제보 유형(무의미 후보명 노출) 재발 방지

## 6) 의사결정 필요 사항
1. 운영 API 기준 도메인 단일화 필요
- 현재 `https://2026-api.up.railway.app`는 404(Application not found),
  `https://2026-api-production.up.railway.app`는 동작 중.
- 문서/환경변수/런북/검증 기준을 한 도메인으로 고정해야 혼선이 사라짐.

2. 후보 상세 fallback 정책 확정 필요
- 현재는 `name_ko` 누락 시 `candidate_id` fallback 적용.
- UI 정책상 `미확정(검수대기)` 고정 문구를 선호하면 후속 패치로 통일 가능.

## 7) 산출물
- 코드 수정:
  - `app/services/repository.py`
  - `app/api/routes.py`
  - `tests/test_repository_matchup_scenarios.py`
  - `tests/test_api_routes.py`
- 보고서:
  - `develop_report/2026-02-26_issue345_operational_data_quality_hotfix_report.md`

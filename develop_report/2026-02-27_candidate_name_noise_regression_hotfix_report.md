# 2026-02-27 Candidate Name Noise Regression Hotfix Report

## 1) 작업 개요
- 대상 이슈: `#485` `[DEVELOP][P0] 후보 비인명 토큰 노출 회귀 핫픽스(서울시장 11-000)`
- 목적: runtime 하드가드 이후 후보 옵션의 유효성 신호(`name_validity`)를 응답 계약에 명시하고, invalid 토큰은 계속 응답에서 제거.

## 2) 구현 변경 사항
1. 응답 스키마 확장
- 파일: `/app/models/schemas.py`
- 변경: `MatchupOptionOut`에 `name_validity` 필드 추가
  - enum: `valid | invalid | unknown`
  - 기본값: `unknown`

2. 리포지토리 값 채움
- 파일: `/app/services/repository.py`
- `_normalize_options()`에서 `name_validity` 계산 추가
  - `candidate_id` 존재 또는 정당 확정 시 `valid`
  - 그 외 `unknown`
- noise 토큰은 기존 runtime 필터에서 계속 제거되므로, 응답에 `invalid` 옵션은 노출되지 않음.

3. 문서 계약 동기화
- 파일: `/docs/03_UI_UX_SPEC.md`
- `GET /api/v1/matchups/{matchup_id}` 필수 필드에 `options[].name_validity` 명시.

4. 테스트 보강
- 파일: `/tests/test_api_routes.py`
  - matchup 옵션 응답에 `name_validity="valid"` 검증 추가
- 파일: `/tests/test_repository_matchup_scenarios.py`
  - scenario options 전 항목에 `name_validity` 키 존재 검증 추가

## 3) 검증
- 실행:
  - `pytest -q tests/test_repository_matchup_scenarios.py tests/test_api_routes.py -k "matchup"`
- 결과:
  - `12 passed`

## 4) 수용 기준 매핑
- [x] API/UI 단계 비인명 토큰 회귀 차단 체계 유지
- [x] 후보 옵션 `name_validity` 신호 추가
- [x] 문서/테스트 동기화 완료

## 5) 의사결정 필요 사항
- 없음.

## 6) 변경 파일
- `/app/models/schemas.py`
- `/app/services/repository.py`
- `/docs/03_UI_UX_SPEC.md`
- `/tests/test_api_routes.py`
- `/tests/test_repository_matchup_scenarios.py`
- `/develop_report/2026-02-27_candidate_name_noise_regression_hotfix_report.md`

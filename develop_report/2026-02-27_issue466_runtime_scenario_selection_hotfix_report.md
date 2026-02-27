# 2026-02-27 Issue466 Runtime Scenario Selection Hotfix Report

## 1) 배경
- `#466`는 개발 완료 후 QA 재검증에서 `status/blocked`로 전환됨.
- 차단 근거: 부산시장(`2026_local|광역자치단체장|26-000`) 응답의 `scenario_count=1`, `scenario_key=['default']`.

## 2) 원인 분석
- 기존 선택 로직은 최근 observation 중 첫 유효 row를 우선 채택.
- 운영 데이터에서는 최신 row가 `default` 2옵션(양자 1개)이고,
  더 이전 row가 명시적 시나리오 3개(`h2h/h2h/multi`)를 보유.
- 결과적으로 풍부한 시나리오 row가 있음에도 최신 최소 row가 선택되어 QA 수용기준 미충족.

## 3) 수정 내용
1. `app/services/repository.py`
- `_select_matchup_observation_bundle()`에 품질 기반 선택 점수 추가:
  - `scenario_count>=3` 우선
  - explicit scenario(`scenario_key != default`) 보유 우선
  - scenario 수, option 수 순으로 우선
- 동일 점수에서는 기존 정렬(최신 우선) 유지.

2. `tests/test_repository_matchup_scenarios.py`
- 신규 회귀 테스트 추가:
  - 최신 observation이 `default` 최소 옵션(2개)일 때,
    이전 observation의 풍부 시나리오(3개)를 우선 선택하는지 검증.

## 4) 검증
1. 테스트
- `pytest tests/test_repository_matchup_scenarios.py -q` -> `7 passed`
- `pytest tests/test_api_routes.py -k "matchup" -q` -> `4 passed`

2. 실DB 함수 검증(코드 기준)
- DB: Supabase production 연결
- 호출: `PostgresRepository.get_matchup('2026_local|광역자치단체장|26-000')`
- 결과:
  - `pollster='KSOI'`
  - `survey_end_date='2026-01-03'`
  - `scenario_count=3`
  - `scenario_keys=['h2h-전재수-김도읍','h2h-전재수-박형준','multi-전재수']`

## 5) 기대 효과
- QA 차단 조건인 부산시장 시나리오 분리(3개) 미충족 문제를 API 선택 정책 차원에서 해소.
- legacy `options[]` 하위호환은 유지.

## 6) 의사결정 필요 사항
- 없음.

## 7) 변경 파일
- `/app/services/repository.py`
- `/tests/test_repository_matchup_scenarios.py`
- `/develop_report/2026-02-27_issue466_runtime_scenario_selection_hotfix_report.md`

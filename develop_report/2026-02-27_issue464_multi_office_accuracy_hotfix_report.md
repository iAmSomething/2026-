# 2026-02-27 Develop Issue464 Multi Office Accuracy Hotfix Report

## Scope
- Issue/PR: #464 (multi scenario mix + office/region mis-mapping hotfix)

## Changes
1. `app/services/ingest_service.py`
- multi 시나리오(다자대결) 파싱을 강화해 양자 수치 혼입 차단
- 조사/기사 제목의 선거 의도를 재판별해 `office_type`, `region_code`, `matchup_id` 교정
  - 예: 부산시장 -> `광역자치단체장`, `26-000`

2. `tests/test_ingest_service.py`
- 다자 8인 수치 보존 검증(전재수/박형준/김도읍/조경태/조국/박재호/이재성/윤택근)
- 부산시장 오매핑 교정 검증 추가

3. `tests/test_issue339_scenario_separation_reprocess_script.py`
- runtime acceptance의 다자 후보 집합 검증을 8인 기준으로 보강

## Validation
- `.venv313/bin/pytest -q tests/test_ingest_service.py tests/test_issue339_scenario_separation_reprocess_script.py`
- `.venv313/bin/pytest -q tests/test_repository_matchup_scenarios.py`
- reported result: total 32 passed

## Expected Runtime Impact
- 부산시장 케이스에서 `기초자치단체장|26-710` 오분류를 방지
- 다자/양자 시나리오 카드에서 수치 혼입 없이 시나리오별 분리 노출

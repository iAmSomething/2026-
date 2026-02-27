# 2026-02-27 issue #339 scenario canonicalize update12 report

## 1) 작업 개요
- 담당: role/collector
- 대상 이슈: #339 (`[COLLECTOR] ingest baseline restore + strict acceptance`)
- 목적: `explicit scenario + default` 혼합 입력에서 `default` 시나리오 누수가 남는 문제를 제거하고, canonical 시나리오(`h2h-*`, `multi-*`)만 유지.

## 2) 구현 내용
- 파일: `app/services/ingest_service.py`
- 변경:
1. `_repair_candidate_matchup_scenarios(...)`의 기존 early-return 조건을 조정.
- 기존: candidate 시나리오 중 explicit key가 하나라도 있으면 즉시 종료.
- 변경: `explicit only`(default 후보 행이 전혀 없는 경우)일 때만 종료.
2. 혼합 케이스(`explicit + default`) canonicalization 경로를 유지하도록 보강.
- default 후보 행 제거
- `multi-*` 시나리오 정규화(`scenario_type=multi_candidate`, `scenario_title` 보정)
- default에만 있던 후보를 `multi-*`에 보강

## 3) 테스트
- 파일: `tests/test_ingest_service.py`
- 신규 테스트:
1. `test_candidate_matchup_scenarios_drop_default_when_explicit_and_multi_coexist`
- 입력: `h2h-*`, `multi-*`, `default` candidate 행이 혼재된 payload
- 검증:
  - 결과 candidate 시나리오에 `default` 미포함
  - `multi-전재수`에 후보 3인(`전재수`, `박형준`, `김도읍`) 완전 포함
  - `multi` 시나리오 타입이 `multi_candidate`로 통일

- 실행 결과:
1. `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py` -> `15 passed`
2. `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_collector_live_coverage_v2_pack_script.py` -> `4 passed`

## 4) 현재 상태
- 코드/테스트 로컬 검증 완료.
- 다음 단계: PR 생성 후 merge, main에서 runtime acceptance 재측정.

## 5) 리스크 및 블로커
- 기능 레벨 canonicalization은 단위테스트로 확인됨.
- 다만 운영 runtime acceptance 최종 PASS는 `ingest-schedule` 워크플로 재실행 확인 필요.

## 6) 의사결정 필요사항
1. #357(ingest-schedule timeout) 우선 처리 순서 확정 필요.
- 본 패치 merge 후에도 스케줄 실행 timeout이 지속되면 #339 acceptance를 즉시 닫을 수 없음.
- 제안: #357을 p0 unblock로 유지하고, #339 검증 run을 그 직후 재실행.

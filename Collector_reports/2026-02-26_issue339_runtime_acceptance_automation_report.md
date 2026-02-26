# #339 운영 수용판정 자동화 보고서

- 작성일시(UTC): 2026-02-26T13:33:00Z
- 담당: Collector
- 관련 이슈: #339
- 상태: in-progress

## 1) decision
- #357 unblock 이후 수동 확인 지연을 줄이기 위해, #339 운영 수용기준(3블록 분리/혼입 0)을 자동 판정하는 runtime check를 `run_issue339_scenario_separation_reprocess.py`에 추가한다.

## 2) next_status
- `status/in-progress`

## 3) 구현 내용
1. `scripts/run_issue339_scenario_separation_reprocess.py`
- 기존 재처리 모드 유지(기본 동작 무변경)
- 신규 runtime 모드 추가: `--runtime-check`
- 입력 지원:
  - 운영 API 직접 조회(`--api-url`)
  - 기존 캡처 JSON 재판정(`--capture-input`)
- 출력:
  - runtime capture JSON (`--capture-output`)
  - runtime acceptance report JSON (`--runtime-report-output`)
- 판정 항목:
  - `scenario_count_ge_3`
  - `has_required_three_blocks`
  - `block_option_mixing_zero`
  - `required_block_values_present`
  - `default_removed`
  - `acceptance_pass`

2. 테스트 추가
- `tests/test_issue339_scenario_separation_reprocess_script.py`
  - default 단일 시나리오 FAIL 케이스
  - 요구 3블록(h2h/h2h/multi) PASS 케이스

## 4) 실행 검증
1. 테스트
- command:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_issue339_scenario_separation_reprocess_script.py tests/test_collector_live_coverage_v2_pack_script.py`
- result: `6 passed`

2. 운영 캡처 재판정(update6 캡처 기준)
- command:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python scripts/run_issue339_scenario_separation_reprocess.py --runtime-check --capture-input data/issue339_runtime_after_capture_blocked_update6.json --capture-output data/issue339_runtime_after_capture_blocked_update6_revalidated.json --runtime-report-output data/issue339_runtime_acceptance_update6.json`
- result:
  - `scenario_count=1`
  - `scenario_keys=["default"]`
  - `acceptance_pass=false`

## 5) evidence
- code: `scripts/run_issue339_scenario_separation_reprocess.py`
- test: `tests/test_issue339_scenario_separation_reprocess_script.py`
- runtime report: `data/issue339_runtime_acceptance_update6.json`
- runtime capture(revalidated): `data/issue339_runtime_after_capture_blocked_update6_revalidated.json`

## 6) 다음 액션
1. #357 green run 발생 즉시 동일 스크립트를 운영 API 직접 조회 모드로 실행
2. `acceptance_pass=true` 결과 및 after capture를 #339에 즉시 첨부
3. QA 재게이트 요청

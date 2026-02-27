# #339 targeted 재적재 성공 및 acceptance PASS 업데이트 v15 보고서

- 작성일시(UTC): 2026-02-27T01:15:10Z
- 담당: Collector
- 관련 이슈: #339, #357
- 상태: in-progress -> done 요청 가능

## 1) decision
- collector 전용 수동 재적재 워크플로(`Collector Issue339 Targeted Reingest`)를 도입해 26-710 단일 레코드 ingest 경로를 분리했다.
- explicit 시나리오 재적재 시 기존 `default` 후보행이 잔존하던 문제를 ingest 코드에서 정리/보강하도록 반영했다.
- 최신 targeted 재적재(run `22468417899`) 후 운영 runtime acceptance가 `acceptance_pass=true`로 전환됨을 확인했다.

## 2) next_status
- `status/done` 전환 요청 (QA PASS 확인 대기)

## 3) 구현/실행 내역
1. collector 전용 targeted 재적재 워크플로 추가
- merged PR: https://github.com/iAmSomething/2026-/pull/429
- workflow: `collector-issue339-targeted-reingest.yml`
- 목적: full live payload timeout과 분리하여 #339 대상(26-710)만 재적재

2. targeted 워크플로 PYTHONPATH hotfix
- merged PR: https://github.com/iAmSomething/2026-/pull/431
- 내용: normalize 단계 `PYTHONPATH=.` 적용 (`ModuleNotFoundError: app` 해소)

3. default 잔존 정리 + multi 보강 코드 반영
- merged PR: https://github.com/iAmSomething/2026-/pull/432
- 내용:
  - explicit 시나리오 ingest 시 기존 DB의 `candidate_matchup/default` 조회
  - multi 블록 누락 후보를 default 값으로 보강
  - 이후 `candidate_matchup/default` 행 삭제
- 테스트:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py` -> 16 passed
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_collector_live_coverage_v2_pack_script.py` -> 4 passed

4. targeted 재적재 런 결과
- run(실패, hotfix 전): https://github.com/iAmSomething/2026-/actions/runs/22468189004
- run(성공, cleanup/backfill 전): https://github.com/iAmSomething/2026-/actions/runs/22468258261
- run(성공, cleanup/backfill 후): https://github.com/iAmSomething/2026-/actions/runs/22468417899
  - `Run issue339 targeted ingest with retry` 1회 성공
  - `http_status=200`, `job_status=success`, `cause_code=null`

## 4) runtime acceptance 결과(최종)
- command:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python scripts/run_issue339_scenario_separation_reprocess.py --runtime-check --capture-output data/issue339_runtime_after_capture_targeted_update15.json --runtime-report-output data/issue339_runtime_acceptance_update15.json`
- capture_at: `2026-02-27T01:14:03.784015+00:00`
- 관측:
  - `scenario_count=3`
  - `scenario_keys=["h2h-전재수-김도읍", "h2h-전재수-박형준", "multi-전재수"]`
  - `default` 제거 확인
- acceptance 판정:
  - `scenario_count_ge_3=true`
  - `has_required_three_blocks=true`
  - `block_option_mixing_zero=true`
  - `required_block_values_present=true`
  - `default_removed=true`
  - `acceptance_pass=true`

## 5) evidence
- final targeted run: https://github.com/iAmSomething/2026-/actions/runs/22468417899
- final run status snapshot: `data/issue339_targeted_run_22468417899_status_snapshot.json`
- final run log: `data/issue339_targeted_run_22468417899.log`
- final ingest report: `data/issue339_targeted_run_22468417899/collector-issue339-targeted-reingest-report/issue339_targeted_ingest_report.json`
- final failure classification: `data/issue339_targeted_run_22468417899/collector-issue339-targeted-reingest-report/issue339_targeted_failure_classification.json`
- runtime capture: `data/issue339_runtime_after_capture_targeted_update15.json`
- runtime acceptance: `data/issue339_runtime_acceptance_update15.json`

## 6) 의사결정 요청
1. #339을 `status/done`으로 전환해도 되는지 확인 요청
- collector acceptance 기준은 충족됨(`acceptance_pass=true`)
- #357은 full schedule 안정화 이슈로 별도 추적 유지 권장

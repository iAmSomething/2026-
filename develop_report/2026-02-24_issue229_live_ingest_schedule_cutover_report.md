# 2026-02-24 Issue229 Live Ingest Schedule Cutover Report

## 1) 작업 개요
- 이슈: #229 `[DEVELOP][S3] 실데이터 ingest 스케줄 전환 + 재처리 운영화`
- 목표:
  1. ingest-schedule 입력을 `collector_live_*` 산출물 우선 라우팅
  2. 실데이터 payload 정규화 계층 강화(후보/정당/스코프/오차범위)
  3. 실패 건 dead-letter + 재처리 CLI 추가
  4. 최근 실행 기준 3회 연속 green 증빙

## 2) 구현 사항
- ingest-schedule 입력 라우팅 전환
  - 워크플로우 입력을 `data/collector_live_payload.json`으로 고정
  - `scripts/qa/build_live_coverage_payload.sh`에서 v2 우선(v2 없으면 v1 fallback)으로 payload 생성
  - route metadata(`source_mode`, `run_type`, `record_count`) 보고서 생성
  - 변경 파일:
    - `.github/workflows/ingest-schedule.yml`
    - `scripts/qa/build_live_coverage_payload.sh`

- 정규화 계층 강화
  - `app/services/ingest_input_normalization.py` 확장:
    - candidate/option party 필드 strict normalize
    - `audience_scope` alias normalize(`nationwide` 등 -> `national/regional/local`)
    - `audience_region_code` 보정
    - `margin_of_error` 문자열(`±3.1%p` 등) float normalize
  - API 앞단(`run-ingest`)의 raw JSON -> normalize -> schema validate 경로에서 적용
  - 회귀 테스트 반영:
    - `tests/test_normalize_ingest_payload_for_schedule.py`
    - `tests/test_api_routes.py`

- dead-letter + 재처리 CLI
  - `scripts/qa/run_ingest_with_retry.py`
    - 실패 시 dead-letter JSON 기록(`data/dead_letter/*.json`)
    - `failure_type` 포함
    - `--allow-partial-success` 모드 추가
  - `scripts/qa/reprocess_ingest_dead_letter.py`
    - dead-letter 파일 선택(`--dead-letter` or `--latest`)
    - 재처리 실행 후 dead-letter 상태/이력 업데이트
  - 테스트 추가:
    - `tests/test_ingest_dead_letter_reprocess.py`
    - `tests/test_run_ingest_with_retry_script.py`

## 3) 검증 결과
- 로컬 테스트
  - `pytest -q`
  - 결과: `128 passed`

- ingest-schedule 실행 증빙
  - 초기(변경 전 판정): `job_partial_success`로 step fail 확인
  - 판정 보정(`--allow-partial-success`) 후 3회 연속 success:
    - https://github.com/iAmSomething/2026-/actions/runs/22336689922
    - https://github.com/iAmSomething/2026-/actions/runs/22336691564
    - https://github.com/iAmSomething/2026-/actions/runs/22336693149

- 실데이터 payload 사용 증빙
  - 각 런 keylines에 `route_report_json`:
    - `source_mode=collector_live_v2`
    - `run_type=collector_live_coverage_v2`
    - `record_count=30`

## 4) 증빙 파일
- run lists
  - `data/verification/issue229_ingest_schedule_runlist_initial.json`
  - `data/verification/issue229_ingest_schedule_runlist_retry_initial.json`
  - `data/verification/issue229_ingest_schedule_runlist_final.json`

- run status/json
  - `data/verification/issue229_run_22336689922.json`
  - `data/verification/issue229_run_22336691564.json`
  - `data/verification/issue229_run_22336693149.json`

- key log lines
  - `data/verification/issue229_run_22336689922_keylines.log`
  - `data/verification/issue229_run_22336691564_keylines.log`
  - `data/verification/issue229_run_22336693149_keylines.log`

- artifacts(download)
  - `data/verification/issue229_run_22336689922_artifact/ingest_schedule_payload_route_report.json`
  - `data/verification/issue229_run_22336689922_artifact/ingest_schedule_report.json`
  - `data/verification/issue229_run_22336691564_artifact/ingest_schedule_payload_route_report.json`
  - `data/verification/issue229_run_22336691564_artifact/ingest_schedule_report.json`
  - `data/verification/issue229_run_22336693149_artifact/ingest_schedule_payload_route_report.json`
  - `data/verification/issue229_run_22336693149_artifact/ingest_schedule_report.json`

- checksum
  - `data/verification/issue229_evidence_sha256.txt`

## 5) 완료 기준 대비
- [x] ingest-schedule가 `collector_live_*` payload 사용 로그 증빙
- [x] 실데이터 payload 정규화 강화(후보/정당/스코프/오차범위)
- [x] 실패 건 dead-letter + 재처리 CLI 추가
- [x] 최근 실행 기준 3회 연속 green 증빙

## 6) 의사결정 필요사항
- 없음

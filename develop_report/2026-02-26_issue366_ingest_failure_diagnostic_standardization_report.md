# 2026-02-26 Issue366 Ingest Failure Diagnostic Standardization Report

## 1) 배경
- ingest 실패 시 `http_5xx`/`http_4xx` 수준의 거친 분류만 남아 DB/Auth/Schema/Timeout 조치 경로가 즉시 분리되지 않는 문제가 있었습니다.
- 목표는 run 단위 원인코드 표준화 + 아티팩트 일관화 + 실패 코멘트 템플릿 표준화입니다.

## 2) 구현 내용

### A. ingest runner 원인코드(cause_code) 표준화
- 파일: `app/jobs/ingest_runner.py`
- 변경:
  - `AttemptLog`, `IngestRunnerResult`에 `cause_code` 필드 추가
  - `_derive_cause_code()` 신규 구현
  - 분류 규칙(핵심):
    - DB/Auth: `db_auth_failed`
    - DB/Schema: `db_schema_mismatch`, `schema_payload_contract_422`
    - DB/Config/연결: `db_config_missing`, `db_connection_error`, `db_connection_unknown`, `db_network_error`, `db_uri_invalid`, `db_ssl_required`
    - Timeout: `timeout_request`, `db_timeout`
    - HTTP fallback: `http_5xx`, `http_4xx`, `http_408`, `http_429`, `http_<status>`

### B. ingest retry 스크립트 진단/코멘트 템플릿 확장
- 파일: `scripts/qa/run_ingest_with_retry.py`
- 변경:
  - `--comment-template-path` 인자 추가
  - classification artifact에 `runner.cause_code`, `attempt_timeline[].cause_code` 저장
  - 실패 시 `write_failure_comment_template()`로 표준 코멘트 초안 파일 생성
  - 표준 코멘트 초안은 계약키(`report_path`, `evidence`, `next_status`) 포함

### C. Ingest Schedule workflow 아티팩트 표준화
- 파일: `.github/workflows/ingest-schedule.yml`
- 변경:
  - `run_ingest_with_retry.py` 실행 시
    - `--classification-artifact data/ingest_schedule_failure_classification.json`
    - `--comment-template-path data/ingest_schedule_failure_comment_template.md`
  - `if: always()` 단계에서 진단 아티팩트 fallback 생성 보강
  - 업로드 대상에 아래 파일 추가:
    - `data/ingest_schedule_failure_classification.json`
    - `data/ingest_schedule_failure_comment_template.md`

### D. Collector workflow fallback 동기화
- 파일: `.github/workflows/collector-live-news-schedule.yml`
- 변경:
  - fallback classification artifact 생성 시 `runner.cause_code` 포함

### E. 운영 문서 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 변경:
  - ingest schedule 진단 아티팩트 경로 추가
  - `cause_code` 표준 분류표/운영 목적 문서화

## 3) 테스트 및 검증

### 단위 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_ingest_runner.py tests/test_run_ingest_with_retry_script.py`
- 결과:
  - `12 passed`

### workflow YAML 검증
- 명령:
  - `bash scripts/qa/validate_workflow_yaml.sh`
- 결과:
  - `.github/workflows/*.yml` 파싱 성공

## 4) 수용기준 대응
1. 실패 run 1건에서 원인코드 확인 가능
- `ingest_schedule_failure_classification.json`의 `runner.cause_code` / `attempt_timeline[].cause_code`로 확인 가능
2. 동일 유형 실패 재현 시 코드 일치
- `db_auth_failed`, `db_schema_mismatch`, `timeout_request` 케이스를 단위테스트로 고정
3. 보고서 제출
- 본 문서 제출

## 5) 반영 파일
- `app/jobs/ingest_runner.py`
- `scripts/qa/run_ingest_with_retry.py`
- `.github/workflows/ingest-schedule.yml`
- `.github/workflows/collector-live-news-schedule.yml`
- `tests/test_ingest_runner.py`
- `tests/test_run_ingest_with_retry_script.py`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`

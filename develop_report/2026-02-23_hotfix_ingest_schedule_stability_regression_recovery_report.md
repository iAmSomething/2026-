# 2026-02-23 HOTFIX ingest-schedule 안정성 회귀(422/timeout) 복구 보고서 (#216)

## 1) 배경
- 실패 재현:
  - run `22299220265`: `ReadTimeout` (retry 3회 실패)
  - run `22297895813`: `ReadTimeout`
  - run `22297786360`: `HTTP 422` (candidate payload 스키마 불일치)
- 기존 정책은 timeout 경계(180s)에서 변동성에 취약했고, 실패 분류가 `failure_reason` 단일 문자열 중심이라 422/timeout 구분 자동판단이 어려웠음.

## 2) 변경 사항
1. `run_ingest_with_retry` 실패 분류/정책 고도화
- 파일: `app/jobs/ingest_runner.py`
- 추가:
  - attempt 단위 `failure_class` (`payload_contract_422`, `timeout`, `http_5xx` 등)
  - attempt 단위 `request_timeout_seconds`
  - 결과 단위 `failure_class`
- 정책:
  - `payload_contract_422`/일반 `http_4xx`는 즉시 비재시도
  - `timeout`/`http_408`/`http_429`/`http_5xx`/`request_error`는 재시도
  - timeout 발생 시 다음 시도 timeout 자동 스케일업

2. CLI 파라미터 확장
- 파일: `scripts/qa/run_ingest_with_retry.py`
- 추가 옵션:
  - `--timeout-scale-on-timeout`
  - `--timeout-max`
- 출력 필드에 `failure_class` 포함

3. ingest-schedule 워크플로 튜닝
- 파일: `.github/workflows/ingest-schedule.yml`
- 변경:
  - `--max-retries 1`
  - `--backoff-seconds 3`
  - `--timeout 240`
  - `--timeout-scale-on-timeout 1.5`
  - `--timeout-max 420`

4. 회귀 테스트 보강
- 파일: `tests/test_ingest_runner.py`
- 추가 검증:
  - 422 계약 오류 비재시도
  - timeout 시 timeout 스케일업 적용

## 3) 검증 결과
- 로컬 테스트: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q` -> `114 passed`
- ingest-schedule 연속 2회 green (workflow_dispatch):
  - run `22300936942` success
  - run `22301134416` success

## 4) 완료 기준 매핑
1. 후보 필드 정합화
- 기존 #210에서 반영된 `scripts/qa/normalize_ingest_payload_for_schedule.py`를 유지 활용.
- 422 재현 로그(`22297786360`)를 증빙으로 보존.

2. timeout/backoff 정책 재조정 + 실패 유형 분리
- 이번 #216에서 `failure_class` 분리 및 유형별 재시도/timeout 스케일 정책 반영 완료.

3. 스케줄 안정성 증빙
- 동일 브랜치에서 연속 2회 dispatch green 확보 완료.

## 5) 증빙 파일
- `data/verification/issue216_ingest_stability_pytest.log`
- `data/verification/issue216_run_22299220265_failure.json`
- `data/verification/issue216_run_22297786360_failed_422.log`
- `data/verification/issue216_run_22300936942_success.json`
- `data/verification/issue216_run_22300936942_artifact/ingest_schedule_report.json`
- `data/verification/issue216_run_22301134416_success.json`
- `data/verification/issue216_run_22301134416_artifact/ingest_schedule_report.json`
- `data/verification/issue216_ingest_stability_sha256.txt`

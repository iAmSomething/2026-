# [DEVELOP] #264 collector schedule 관측성 표준화 v1 보고서

- 작성일: 2026-02-25
- 담당: role/develop
- 이슈: https://github.com/iAmSomething/2026-/issues/264
- 브랜치: `codex/issue260-ingest-hang-guard` (공유 구현)

## 1) 목표
- collector schedule 성공/실패 런에서 타임라인 추적 가능성 확보
- 실패 아티팩트만으로 1차 원인 분류 가능하도록 표준 스키마 확정
- `/api/v1/dashboard/summary` 지연 원인 파악용 최소 진단 필드 설계 제안 정리

## 2) 표준화 반영
1. 실행 타임라인 표준
- 소스: `app/jobs/ingest_runner.py`
- 표준 이벤트:
  - `run_start`
  - `attempt_start`
  - `attempt_waiting` (heartbeat)
  - `attempt_result`
  - `retry_wait`
  - `timeout_scaled`
  - `run_end`
- attempt 로그 표준 필드:
  - `attempt`, `started_at`, `finished_at`, `duration_seconds`
  - `request_timeout_seconds`, `next_backoff_seconds`
  - `http_status`, `job_status`, `failure_class`, `failure_type`
  - `error`, `detail`

2. 실패 분류 아티팩트 스키마 v1
- 파일: `data/collector_live_news_v1_failure_classification.json`
- 스키마 버전: `collector_ingest_failure_classification.v1`
- 최상위 필드:
  - `generated_at`, `source_input_path`, `payload_run_type`, `payload_record_count`
  - `runner{ success/raw_success/attempt_count/run_ids/elapsed_seconds/failure_* }`
  - `runner.failure_class_counts`, `runner.timeout_attempts`
  - `attempt_timeline[]`
  - `dead_letter_path`

3. 아티팩트 업로드 표준
- 소스: `.github/workflows/collector-live-news-schedule.yml`
- `if: always()` 업로드 기준:
  - runner report
  - failure classification
  - api log snapshot
  - dead-letter json

## 3) 성공/실패 타임라인 샘플 정의
1. success 샘플(개념)
- `run_start` -> `attempt_start(1)` -> `attempt_waiting(반복)` -> `attempt_result(success)` -> `run_end(success)`

2. failure(timeout) 샘플(개념)
- `run_start` -> `attempt_start(1)` -> `attempt_waiting(반복)` -> `attempt_result(timeout)` -> `retry_wait` -> `timeout_scaled` -> `attempt_start(2)` ... -> `run_end(failure)`

## 4) `/api/v1/dashboard/summary` 최소 진단 필드 제안
1. 제안 필드
- `last_ingest_status`
- `last_ingest_failure_class`
- `last_ingest_elapsed_seconds`
- `last_ingest_attempt_count`
- `last_ingest_timeout_attempts`
- `last_ingest_artifact_ref`

2. 소스 매핑
- `ingestion_runs`
- `collector_live_news_v1_ingest_runner_report.json`
- `collector_live_news_v1_failure_classification.json`

3. 공개 API 가드
- 민감정보/원문 payload 미노출
- 분류 요약 필드 중심 제공, 상세 디버그는 내부 아티팩트/로그에서 확인

## 5) 의사결정 필요 사항
1. `/api/v1/dashboard/summary` 진단 필드 적용 시점
- 제안만 본 이슈에서 확정, 실제 API 반영은 후속 develop 이슈로 분리 권장

# [DEVELOP] #260 collector-live ingest 장시간 in_progress 가드 핫픽스 보고서

- 작성일: 2026-02-25
- 담당: role/develop
- 이슈: https://github.com/iAmSomething/2026-/issues/260
- 브랜치: `codex/issue260-ingest-hang-guard`

## 1) 배경
- `Collector Live News Schedule` 런에서 `Run ingest with retry` 단계가 장시간 in_progress로 보이며 QA 판정이 지연됨.
- 목표: 모호한 장시간 정체를 없애고(경계시간 내 종료), 로그/아티팩트만으로 실패 원인 분류 가능하게 개선.

## 2) 반영 내용
1. workflow timeout guard
- 파일: `.github/workflows/collector-live-news-schedule.yml`
- 반영:
  - job `timeout-minutes: 25`
  - step `Build live news payload`: `timeout-minutes: 10`
  - step `Start API server`: `timeout-minutes: 3`
  - step `Run ingest with retry`: `timeout-minutes: 15`

2. ingest runner heartbeat/timeline 강화
- 파일: `app/jobs/ingest_runner.py`
- 반영:
  - 이벤트 로그 콜백(`event_log_fn`) + heartbeat(`heartbeat_interval_seconds`) 지원
  - 이벤트: `run_start`, `attempt_start`, `attempt_waiting`, `attempt_result`, `retry_wait`, `timeout_scaled`, `run_end`
  - attempt 타임라인 필드 확장: `started_at`, `finished_at`, `duration_seconds`, `next_backoff_seconds`
  - 러너 결과 필드 확장: `started_at`, `elapsed_seconds`

3. 실패 원인 분류 아티팩트 표준화
- 파일: `scripts/qa/run_ingest_with_retry.py`
- 반영:
  - `--classification-artifact` 옵션 추가
  - 스키마: `collector_ingest_failure_classification.v1`
  - 핵심 필드:
    - `runner.failure_class/failure_type/failure_reason`
    - `runner.failure_class_counts`, `runner.timeout_attempts`
    - `attempt_timeline[]`, `dead_letter_path`
  - heartbeat JSON 로그 출력(`channel=ingest_runner_heartbeat`)

4. 실패 상황 진단 산출물 보강
- 파일: `.github/workflows/collector-live-news-schedule.yml`
- 반영:
  - `Capture API log snapshot` (`/tmp/collector-live-news-api.log -> data/collector_live_news_api.log`)
  - `Upload artifacts`를 `if: always()`로 실행
  - 업로드 대상 확장:
    - `data/collector_live_news_v1_failure_classification.json`
    - `data/collector_live_news_api.log`
    - `data/dead_letter/*.json`

## 3) 검증
1. YAML 파싱
- 실행: `bash scripts/qa/validate_workflow_yaml.sh`
- 결과: pass

2. Python 구문
- 실행: `python3 -m py_compile app/jobs/ingest_runner.py scripts/qa/run_ingest_with_retry.py`
- 결과: pass

3. 테스트
- `pytest` 실행 환경 부재로 로컬 단위테스트 미실행 (`pytest_not_available`)
- CI 체크에서 검증 예정

## 4) 완료 기준 매핑
- bounded 종료: workflow/job/step timeout guard 반영 완료
- 로그 원인 구분: heartbeat + attempt timeline + retry/timeout scaling 이벤트 반영 완료
- 실패 원인 분류 아티팩트: 표준 JSON 스키마 반영 및 always upload 구성 완료

## 5) 의사결정 필요 사항
1. 없음

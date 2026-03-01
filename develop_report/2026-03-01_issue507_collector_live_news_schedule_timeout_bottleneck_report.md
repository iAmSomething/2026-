# [DEVELOP] #507 Collector Live News Schedule timeout 병목 제거 보고서

- 작성일: 2026-03-01
- 담당: role/develop
- 이슈: https://github.com/iAmSomething/2026-/issues/507
- 브랜치: `codex/issue507-collector-live-timeout-bottleneck`

## 1) 목표
- `Collector Live News Schedule`의 timeout_request 재발 구간에서 실패율을 낮추고 자동 축소/분할 재시도로 회복성을 확보.
- 실패 시 원인 분류 및 dead-letter 연계를 유지하면서, 평균/95p 실행시간을 아티팩트로 남기도록 표준화.

## 2) 반영 변경
1. timeout 기반 chunk downshift 실행기 추가
- 파일: `scripts/qa/run_ingest_with_retry.py`
- 반영:
  - 신규 옵션
    - `--enable-timeout-chunk-downshift`
    - `--chunk-target-records`
    - `--chunk-min-records`
    - `--chunk-downshift-factor`
    - `--max-chunk-splits`
    - `--max-total-chunks`
  - 신규 로직: `execute_ingest_with_adaptive_chunks(...)`
    - timeout 계열(`failure_class=timeout` 또는 `cause_code=timeout_request`) 실패 청크만 분할 재시도
    - 비-timeout 실패는 즉시 종결(불필요 재시도 방지)
    - idempotent 전제를 유지한 상태로 청크 단위 재호출
  - 결과 리포트 확장
    - `raw_success`, `effective_success`
    - `chunking`(initial/completed/split/max_queue_depth)
    - `latency_profile`(attempt/chunk avg, p95, total)

2. collector live schedule 워크플로 운영값 재설계
- 파일: `.github/workflows/collector-live-news-schedule.yml`
- 반영:
  - job timeout: `35m`
  - ingest step timeout: `22m`
  - ingest 실행 파라미터 변경
    - `--max-retries 1`
    - `--timeout 180 --timeout-scale-on-timeout 1.5 --timeout-max 360`
    - downshift 활성화: `target=80`, `min=15`, `factor=0.5`, `max_splits=8`, `max_total_chunks=20`
  - `Build latency profile artifact` 단계 추가
    - `data/collector_live_news_v1_ingest_runner_report.json`에서 핵심 지표 추출
    - `data/collector_live_news_v1_latency_profile.json` 생성/업로드

3. 단위 테스트 확장
- 파일: `tests/test_run_ingest_with_retry_script.py`
- 반영:
  - timeout 청크 분할 성공 케이스 검증
  - non-timeout 실패 즉시 종결 케이스 검증
  - raw/effective success 분리 검증

## 3) 검증 증빙
### A. 테스트 증빙
- 명령:
  - `source .venv/bin/activate && pytest -q tests/test_run_ingest_with_retry_script.py tests/test_ingest_runner.py tests/test_ingest_dead_letter_reprocess.py`
- 결과:
  - `17 passed in 0.12s`

### B. API 응답 증빙
- 명령(로컬 임시 기동):
  - `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8111`
  - `curl -fsS http://127.0.0.1:8111/health`
  - `curl -fsS http://127.0.0.1:8111/health/db`
- 결과:
  - `/health` -> `{"status":"ok"}`
  - `/health/db` -> `{"status":"ok","db":"ok","ping":true,"bootstrap":{"enabled":false,"attempted":false,"ok":null,"detail":"disabled"}}`

### C. 워크플로 정합성 검증
- 명령:
  - `bash scripts/qa/validate_workflow_yaml.sh`
- 결과:
  - `.github/workflows/*.yml` 파싱 성공

## 4) 수용기준 매핑
1. 스케줄 3회 연속 green
- 코드/워크플로 반영 완료.
- 최종 확인은 PR 반영 후 `collector-live-news-schedule` 3회 연속 성공 런으로 닫음.

2. 평균/95p 실행시간 보고
- `latency_profile`를 ingest 리포트 및 별도 아티팩트(`collector_live_news_v1_latency_profile.json`)로 표준화 완료.

3. timeout_request 원인 분류 및 재발방지 문서화
- timeout 전용 분할 재시도와 non-timeout 즉시 종결을 코드에 분리 반영.
- failure classification artifact에 `chunking_summary`, `latency_profile` 포함.

## 5) 의사결정 필요 사항
1. 수용기준의 `3회 연속 green` 판정 기준 확정 필요
- 제안: `main` 기준 `workflow_dispatch` 3회 연속 성공을 종료 기준으로 고정
- 대안: `main` 2회 + 정시 스케줄 1회 성공도 동일 인정

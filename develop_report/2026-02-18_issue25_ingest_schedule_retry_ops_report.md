# 이슈 #25 보고서: 2시간 주기 ingest 자동실행 + 재시도 운영화

- 이슈: https://github.com/iAmSomething/2026-/issues/25
- 작성일: 2026-02-18
- 담당: develop

## 1. 구현 사항
1. 내부 API 배치 실행 + 재시도 모듈
- `app/jobs/ingest_runner.py`
- 동작: `/api/v1/jobs/run-ingest` 호출, 실패(네트워크/5xx/partial_success) 시 최대 2회 재시도

2. 실행 CLI 추가
- `scripts/qa/run_ingest_with_retry.py`
- 리포트 JSON 저장 기능 포함

3. 스케줄러 구성
- `.github/workflows/ingest-schedule.yml`
- 트리거: 2시간 주기(`0 */2 * * *`) + 수동 실행(`workflow_dispatch`)
- 실행 흐름: API 서버 기동 -> ingest retry 실행 -> 결과 아티팩트 업로드

4. 실패 시 review_queue 연계 안정화
- `app/services/ingest_service.py`에서 예외 시 transaction rollback 후 review_queue 적재
- `app/services/repository.py`에 rollback 메서드 추가

5. 운영 문서/가이드 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md` 자동 실행/재시도 운영 규칙 추가
- `README.md` 실행 커맨드 추가

## 2. 검증 결과
1. 자동실행 2회 증빙
- `data/ingest_schedule_run1_report.json` -> run_ids: `[7]`, success=true
- `data/ingest_schedule_run2_report.json` -> run_ids: `[8]`, success=true

2. 실패/재시도 시나리오 증빙
- 실패 입력: `data/sample_ingest_failure_missing_region.json`
- 결과: `data/ingest_retry_failure_report.json`
  - attempts: 3회
  - 각 attempt `job_status=partial_success`
  - run_ids: `[12, 13, 14]`
  - success=false (재시도 후에도 실패 유지)

3. review_queue 연계 점검
- `review_queue_total=3`
- `review_queue_ingestion_error=3`
- latest: `obs-fail-20260218-missing-region | ingestion_error`

4. 테스트
- 실행: `.venv/bin/pytest -q`
- 결과: `33 passed`

## 3. 변경 파일
- `.github/workflows/ingest-schedule.yml`
- `app/jobs/ingest_runner.py`
- `scripts/qa/run_ingest_with_retry.py`
- `data/sample_ingest_failure_missing_region.json`
- `data/ingest_schedule_run1_report.json`
- `data/ingest_schedule_run2_report.json`
- `data/ingest_retry_failure_report.json`
- `app/services/ingest_service.py`
- `app/services/repository.py`
- `tests/test_ingest_runner.py`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
- `README.md`

## 4. 결론
- 이슈 #25 완료기준 충족
  - 자동실행 2회 이상 증빙
  - 실패/재시도 1건 검증
  - 보고서 제출 완료

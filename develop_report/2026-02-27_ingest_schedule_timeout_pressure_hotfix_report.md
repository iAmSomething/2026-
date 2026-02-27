# 2026-02-27 Ingest Schedule Timeout Pressure Hotfix Report

## 변경 요약
- 대상: `.github/workflows/ingest-schedule.yml`
- 조치:
  - 스케줄 ingest payload 크기 축소: 30건 -> 12건
  - retry amplification 방지: `--max-retries 2` -> `--max-retries 0`
  - 단일 시도 timeout 상향: `--timeout 180` -> `--timeout 420`
  - timeout 상한 동기화: `--timeout-max 360` -> `--timeout-max 420`

## 원인 진단
- 기존 실패는 DB 인증 실패가 아니라 ingest API 응답 지연으로 인한 `timeout_request`였다.
- 증거(run 22467650760): 180s -> 270s -> 360s 3회 모두 `ReadTimeout`.

## 검증 결과
- 패치 브랜치 수동 실행(run 22468509360): workflow 전체 `success`.
- 핵심 로그:
  - `payload_downsize before=30 after=12 max=12`
  - `health_db_http_status=200`
  - ingest step 1회 수행 후 `accepted_partial_success=true`로 종료

## 판단
- 타임아웃 반복 실패(최대 820s 소요) 경로는 해소됨.
- 다만 ingest 결과가 `job_status=partial_success`이므로 데이터 품질/에러 레코드 비율은 별도 추적 필요.

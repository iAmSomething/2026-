# 2026-02-21 Issue #165 Ingest Schedule 연속 실패 복구 v2 보고서

## 1. 배경/원인
- 연속 실패 런: `22255577275`, `22255638221`, `22255662831`, `22255775694`
- 확인된 원인
1. payload 빌드 단계에서 스크립트 경로/모듈 로딩 실패가 발생해 초기 단계에서 중단
2. `run_ingest_with_retry` 실패 시 콘솔에 `success:false`만 표시되어 원인 파악이 어려움
3. 실패 단계에서 아티팩트 업로드가 보장되지 않아 진단 파일 확보가 어려움

## 2. 조치
1. `.github/workflows/ingest-schedule.yml`
- `Run scheduled ingest with retry`에 `--timeout 120` 적용
- `run_ingest` step에 `continue-on-error: true` 적용
- `Collect diagnostics (always)` 추가
  - `data/ingest_schedule_diagnostics.json` 생성
  - API 로그 tail 저장(`data/ingest_schedule_api_tail.log`)
  - 입력 스냅샷 저장(`data/ingest_schedule_input_snapshot.json`)
- `Upload ingest diagnostics artifact`를 `if: always()`로 변경
- `Enforce green status` step 추가로 최종 실패/성공 판정을 단일화

2. `app/jobs/ingest_runner.py`
- attempt 상세 필드(`detail`) 및 최종 `failure_reason` 추가
- 실패 시 `http_status`, `job_status`, `request_error` 기반 원인 문자열 생성
- report JSON에 `failure_reason` 포함

3. `scripts/qa/run_ingest_with_retry.py`
- 실패/성공 공통 출력에 `attempt_count`, `failure_reason`, `last_attempt` 추가

4. `tests/test_ingest_runner.py`
- 성공 케이스 `failure_reason is None` 검증
- 실패 케이스 `failure_reason` 문자열 검증

## 3. 검증
1. 워크플로 Green 증빙
- 수동 실행(run): `22256026677`
- URL: `https://github.com/iAmSomething/2026-/actions/runs/22256026677`
- 결과: `success`

2. 진단 아티팩트 증빙
- artifact name: `ingest-schedule-diagnostics`
- artifact id: `5601064864`
- 포함 파일: report/diagnostics/api tail/input snapshot

3. 런 로그 확인 포인트
- `run_ingest_with_retry` 출력에 `failure_reason`, `last_attempt` 포함
- `Upload ingest diagnostics artifact` step 항상 실행

4. 증빙 파일
- `data/verification/issue165_ingest_schedule_recovery_v2.log`

## 4. 수용 기준 대응
1. 실패 런 진단 가시성: 충족(`if: always` 아티팩트 + diagnostics JSON)
2. false 원인 명시/수정: 충족(`failure_reason`/`last_attempt` 출력)
3. Green 런 1회: 충족(run `22256026677`)

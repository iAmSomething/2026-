# 2026-02-23 Hotfix Ingest Input Normalization Layer Fix Report

## 1) 작업 개요
- 이슈: #220 `[DEVELOP][S2] ingest 입력 정규화 계층 고정(422 재발 방지)`
- 목적: ingest 입력 스키마 불일치(특히 candidate party 필드)로 인한 422 재발 차단
- 범위: API 앞단 정규화 계층 고정, retry 보고 실패 타입 분리, 회귀 테스트 및 스케줄 green 재현 증빙

## 2) 구현 변경 사항
- API 앞단 정규화 고정
  - `/api/v1/jobs/run-ingest`는 raw JSON 수신 후 정규화 유틸 적용, 이후 `IngestPayload` 검증으로 변경
  - 파일: `app/api/routes.py`
- candidate 정규화 유틸 추가
  - `party_inferred`를 strict bool로 정규화
  - `party_inference_source`를 enum(`name_rule/article_context/manual`)으로 정규화
  - 필요 시 문자열 party 단서 값을 `party_name`으로 승격
  - 파일: `app/services/ingest_input_normalization.py`
- 스케줄 정규화 스크립트 공통 유틸화
  - 기존 중복 로직 제거, 서비스 유틸 재사용
  - 파일: `scripts/qa/normalize_ingest_payload_for_schedule.py`
- retry 보고 실패 타입 분리
  - `failure_class` 유지 + `failure_type` 추가(`timeout/http_4xx/http_5xx` 중심)
  - 파일: `app/jobs/ingest_runner.py`, `scripts/qa/run_ingest_with_retry.py`

## 3) 테스트/검증
- 단위/통합 테스트
  - 실행: `pytest tests/test_ingest_runner.py tests/test_normalize_ingest_payload_for_schedule.py tests/test_api_routes.py tests/test_build_live_coverage_payload_script.py -q`
  - 결과: `22 passed`
  - 증빙: `data/verification/issue220_pytest.log`
- 422 재현 payload 정규화 검증
  - 정규화 전제 케이스(`party_inferred` 문자열 + 비허용 source) 입력 후 정규화/스키마 검증 성공
  - 증빙:
    - `data/verification/issue220_422_normalization_success.json`
    - `data/verification/issue220_422_normalization_success.log`
- ingest-schedule 2회 green 재현
  - Run 1: `22302113650` success
  - Run 2: `22302109957` success
  - 증빙:
    - `data/verification/issue220_ingest_schedule_runlist_final.json`
    - `data/verification/issue220_run_22302113650.json`
    - `data/verification/issue220_run_22302109957.json`

## 4) 변경 파일 목록
- `app/api/routes.py`
- `app/jobs/ingest_runner.py`
- `app/services/ingest_input_normalization.py`
- `scripts/qa/normalize_ingest_payload_for_schedule.py`
- `scripts/qa/run_ingest_with_retry.py`
- `tests/test_api_routes.py`
- `tests/test_ingest_runner.py`
- `tests/test_normalize_ingest_payload_for_schedule.py`
- `data/verification/issue220_422_normalization_success.json`
- `data/verification/issue220_422_normalization_success.log`
- `data/verification/issue220_pytest.log`
- `data/verification/issue220_ingest_schedule_runlist_final.json`
- `data/verification/issue220_run_22302113650.json`
- `data/verification/issue220_run_22302109957.json`
- `data/verification/issue220_evidence_sha256.txt`

## 5) 완료 기준 대비
- [x] 422 재현 payload normalize 후 성공 처리
- [x] run_ingest_with_retry 실패 타입 분리(timeout/http_4xx/http_5xx)
- [x] ingest-schedule 2회 green 재현 증빙 확보

## 6) 의사결정 필요사항
- 없음

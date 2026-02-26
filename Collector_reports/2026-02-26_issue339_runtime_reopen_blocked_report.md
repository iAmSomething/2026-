# 2026-02-26 Issue339 Runtime Reopen Blocked Report

## 이슈
- Issue: #339
- 상태: 재오픈 (`status/in-progress`)
- 재오픈 사유: 운영 API 실측에서 `26-710`이 여전히 `scenario_key=default` 단일

## 수행 내역
1. 운영 before 캡처 채취
- endpoint: `GET /api/v1/matchups/2026_local|기초자치단체장|26-710`
- artifact: `data/issue339_runtime_before_capture.json`

2. 운영 재적재 시도 (GitHub Actions)
- workflow: `Ingest Schedule`
- run: `22439048888`
- url: https://github.com/iAmSomething/2026-/actions/runs/22439048888
- 결과: `failure`
- 실패 단계: `Run scheduled ingest with retry`
- 핵심 오류: `http_status=503`, `detail=database connection failed`

3. 운영 after 재캡처 채취
- artifact: `data/issue339_runtime_after_capture_blocked.json`
- 결과: 여전히 `scenario_key=default` 단일

## 실측 결과
- runtime before: `scenario_count=1`, `scenario_keys=["default"]`
- runtime after(attempt): `scenario_count=1`, `scenario_keys=["default"]`
- expected(after reingest): `scenario_keys`에 `h2h-*`, `multi-*` 동시 존재

## 후보-수치 정합 비교 (핵심)
### runtime (default 단일)
- 김도읍 33.2 (`default`)
- 박형준 32.3 (`default`)
- 전재수 26.8 (`default`)

### expected (분리 저장)
- 박형준 32.3 (`multi-전재수`)
- 전재수 43.8 (`h2h-전재수-김도읍`)
- 김도읍 33.2 (`h2h-전재수-김도읍`)
- 전재수 26.8 (`multi-전재수`)

## 수용기준 판정
- `scenario_count>=2`: FAIL
- `h2h-*` + `multi-*` 동시 존재: FAIL
- 혼입 0: FAIL

## 산출물
- `data/issue339_runtime_before_capture.json`
- `data/issue339_runtime_after_capture_blocked.json`
- `data/issue339_runtime_reopen_blocked_report.json`
- `data/issue339_scenario_mix_after.json` (기대 분리 기준)

## 블로커
- 유형: infra/develop
- 내용: ingest job 실행 시 DB 연결 실패(503)로 재적재 불가
- 해소 필요: 운영 DB 연결 복구 후 ingest 재실행

## 의사결정 필요
1. develop/infrastructure에 DB 연결 실패(503) P0 에스컬레이션 여부
2. 복구 즉시 동일 payload 기준 재적재 재실행 및 QA 재게이트 진행 여부

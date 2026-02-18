# 이슈 #10 보고서: 내부 실행 API `/api/v1/jobs/run-ingest` 구현(토큰 인증)

- 이슈: https://github.com/iAmSomething/2026-/issues/10
- 작성일: 2026-02-18
- 담당: develop

## 1. 구현 사항
1. 내부 실행 API 추가
- `POST /api/v1/jobs/run-ingest`
- 요청 바디: `IngestPayload`
- 응답: `{run_id, processed_count, error_count, status}`

2. 토큰 인증 추가
- 헤더: `Authorization: Bearer <token>`
- 환경변수: `INTERNAL_JOB_TOKEN`
- 인증 실패 처리:
  - 헤더 누락/형식 오류 -> `401`
  - 토큰 불일치 -> `403`
  - 서버 토큰 미설정 -> `503`

3. 문서/설정 반영
- `.env.example`에 `INTERNAL_JOB_TOKEN` 추가
- `README.md`에 내부 API 및 보안 설명 갱신

## 2. 테스트
1. 단위/계약 테스트
- 파일: `tests/test_api_routes.py`
- 케이스:
  - 토큰 미제공 시 `401`
  - 잘못된 토큰 시 `403`
  - 올바른 토큰 시 `200` + `status=success`

2. 전체 테스트
- 실행: `.venv/bin/pytest -q`
- 결과: `23 passed`

## 3. 실동작 검증(로컬 실DB)
1. 미토큰 호출
- HTTP `401`
- body: `{"detail":"missing bearer token"}`

2. 유효 토큰 호출
- HTTP `200`
- body: `{"run_id":4,"processed_count":1,"error_count":0,"status":"success"}`

## 4. 변경 파일
- `app/api/dependencies.py`
- `app/api/routes.py`
- `app/config.py`
- `app/models/schemas.py`
- `tests/test_api_routes.py`
- `.env.example`
- `README.md`

## 5. 결론
- 이슈 #10 DoD 충족(구현/문서/테스트 반영 + 보고서 제출)

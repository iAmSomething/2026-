# 2026-02-26 Issue #357 DB Preflight + Diagnostics Update Report

## 1) 작업 목적
- `Ingest Schedule`에서 `health`는 OK인데 `run-ingest`가 503으로 실패하는 케이스를 조기 분리.
- `db_connection_unknown` 발생 시 원인 문자열 분류를 확장해 운영자가 바로 다음 조치를 판단할 수 있도록 개선.

## 2) 변경 사항
1. Ingest Schedule DB 프리플라이트 추가
- 파일: `.github/workflows/ingest-schedule.yml`
- 신규 단계: `DB preflight via health/db`
- 동작: `GET /health/db`의 HTTP status와 body를 출력하고, 200이 아니면 fail-fast 처리.

2. DB 연결 오류 분류 강화
- 파일: `app/db.py`
- `_classify_connection_error` 추가 패턴:
  - `password authentication failed` -> `auth_failed`
  - `authentication failed` -> `auth_error`
  - `no pg_hba.conf entry` -> `auth_error`
  - `server closed the connection unexpectedly` -> `network_error`
  - `connection reset by peer` -> `network_error`
- `DatabaseConnectionError` 메시지에 원본 예외 요약(최대 180자) 포함.
  - 형식: `database connection failed (<reason>): <message>`

3. 테스트 보강
- 파일: `tests/test_db_url_normalization.py`
- 위 신규 분류 케이스 파라미터 테스트 추가.

## 3) 검증 결과
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q \
  tests/test_db_url_normalization.py tests/test_ingest_runner.py
# 23 passed

bash scripts/qa/validate_workflow_yaml.sh
# all workflow files parsed successfully
```

## 4) 기대 효과
- DB 비정상 시 `run-ingest` 재시도 이전에 `/health/db`에서 즉시 원인 출력 가능.
- 기존 `db_connection_unknown`의 일부를 `auth_failed/auth_error/network_error`로 세분화.

## 5) 현재 상태
- 코드 레벨 진단/프리플라이트는 반영 완료.
- 실제 `workflow_dispatch green` 달성 여부는 `main` 반영 후 재실행 결과로 판정 필요.

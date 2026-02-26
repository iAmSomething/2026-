# 2026-02-26 issue357 ingest schedule db503 recovery report

## 1. 이슈
- Issue: #357
- 목표: Ingest Schedule `workflow_dispatch` 1회 GREEN 복구

## 2. 실패 런 분석
- 실패 런: https://github.com/iAmSomething/2026-/actions/runs/22439325982
- 실패 단계: `Run scheduled ingest with retry`
- 증상: 3회 재시도 모두 `http_status=503`, detail=`database connection failed`
- 관측 포인트:
  - preflight에서 `DATABASE_URL` secret 존재는 확인됨
  - 즉, "미설정"이 아니라 "설정값 파싱/접속" 계층 문제 가능성 높음

## 3. 원인 가설
- Supabase URI에서 비밀번호 특수문자(`@`, `!`, `:` 등) 미인코딩 시 libpq 파싱이 깨져 접속 실패 가능.
- 기존 `app/db.py`는 raw `DATABASE_URL`을 그대로 `psycopg.connect()`에 전달하여 해당 케이스를 복구하지 못함.

## 4. 수정
1. `app/db.py`
- `_normalize_database_url()` 추가
  - `postgres://`/`postgresql://` URI를 파싱
  - userinfo의 비밀번호를 `quote(unquote(password), safe="")`로 정규화
  - 마지막 `@` 기준 분리로 비밀번호 내부 `@` 케이스 복구
- `get_connection()`에서 정규화된 URI를 사용해 연결

2. `tests/test_db_url_normalization.py` 추가
- 케이스:
  - 일반 패스워드 unchanged
  - `!` 포함 패스워드 인코딩
  - `@` 포함 패스워드 인코딩
  - 이미 인코딩된 URI idempotent
  - empty 입력

## 5. 검증
1. 실행
```bash
source .venv313/bin/activate && pytest tests/test_db_url_normalization.py tests/test_api_dependencies.py tests/test_api_routes.py
```

2. 결과
- `33 passed`

## 6. 남은 확인(필수)
- main 반영 후 `Ingest Schedule` workflow_dispatch 1회 실행
- `Run scheduled ingest with retry` 단계 success 로그 확인
- green run URL을 #357 코멘트로 첨부

## 7. post-merge dispatch 결과 및 추가 조치
1. post-merge 재실행
- run: https://github.com/iAmSomething/2026-/actions/runs/22439982740
- 결과: failure (동일 단계 `Run scheduled ingest with retry`)
- detail: `http_status=503`, `database connection failed` 지속

2. 추가 개선(진단 강화)
- `.github/workflows/ingest-schedule.yml` 수정:
  - 실패 시 `/tmp/ingest-schedule-api.log` 즉시 출력
  - ingest report/dead-letter artifact를 `if: always()`로 업로드
- 목적: 다음 실행에서 DB 접속 실패 원인(인증/호스트/네트워크)을 로그로 확정

3. 현재 판정
- 코드 상 비밀번호 인코딩 복구 로직 반영은 완료.
- 그러나 운영 secret/접속 대상 상태가 여전히 유효하지 않아 green run 미달성.
- 다음 액션: 진단 강화 워크플로 반영 후 workflow_dispatch 재실행 + 로그 기반 시크릿 교정.

## 8. DB 접속 실패 reason 분류 추가
1. 배경
- API 로그에는 503만 남고 원인 분류가 없어 시크릿/네트워크/SSL 중 즉시 판별이 어려움.

2. 변경
- `app/db.py`
  - `_classify_connection_error()` 추가
  - `DatabaseConnectionError` 메시지에 분류코드 포함:
    - `auth_failed`, `auth_error`, `invalid_host_or_uri`, `connection_refused`, `network_timeout`, `ssl_required`, `unknown`
- `tests/test_db_url_normalization.py`
  - 분류 로직 단위테스트 추가

3. 기대효과
- Ingest Schedule 실패 시 runner detail에 `database connection failed (<reason>)` 노출
- secret 오입력/호스트 오기입/네트워크 계열을 즉시 분기 가능

## 9. API 503 detail 전달 개선
1. 문제
- `get_repository()`에서 `DatabaseConnectionError`를 항상 고정 문자열(`database connection failed`)로 변환해 reason 코드가 누락됨.

2. 수정
- `app/api/dependencies.py`
  - `DatabaseConnectionError` 처리 시 `detail=str(exc)`로 전달하도록 변경.

3. 결과
- Ingest retry 로그의 `detail` 필드에 `database connection failed (<reason>)` 형식으로 분류코드가 노출됨.

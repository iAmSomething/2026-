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

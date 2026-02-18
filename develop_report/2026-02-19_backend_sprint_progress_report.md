# 개발 진행 보고서: 2026-02-19 Backend Sprint Progress

- 작성일: 2026-02-19
- 작성자: 개발 스레드
- 대상: 기획자 전달용

## 1) 작업 지시 대비 완료 상태

### A. 워킹트리 정리 + 커밋 경계 분리
완료. 논리 단위로 커밋 분리함.
1. 백엔드 커밋: `8695ae3`
2. 수집기 커밋: `0dfa5d7`
3. 문서/보고서 커밋: (아래 본 보고서 포함 후 생성)

### B. Python 3.13 `.venv` 실행환경 고정
완료.
1. `.venv` 재구성: Python `3.13.5`
2. 재현 확인:
- `pip install -r requirements.txt` 성공
- `pytest -q` 성공 (`19 passed`)

### C. DB 스키마 + 수동 적재 CLI 실DB 검증
완료(로컬 PostgreSQL 16 실DB 기준).
1. 실DB 준비:
- Homebrew `postgresql@16` 설치
- DB: `election2026_dev`
2. 스키마 적용:
- `python scripts/init_db.py` -> `schema applied`
3. 수동 적재 1회:
- `run_id=1`, `processed_count=1`, `error_count=0`, `status=success`
4. 재적재 2회:
- `run_id=2`, `processed_count=1`, `error_count=0`, `status=success`
5. idempotent 검증(SQL):
- `articles=1`, `poll_observations=1`, `poll_options=3`, `candidates=2`, `regions=1`
- `ingestion_runs=2` (실행 이력만 증가)
6. 정규화/결측 검증(SQL):
- `국정안정론 | 53~55% | min=53 | max=55 | mid=54 | is_missing=false`
- `margin_of_error IS NULL = true`

### D. API 3개 안정화 + 신규 4개 착수
완료.
1. 기존 3개 실DB 응답 확인
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/regions/search`
- `GET /api/v1/candidates/{candidate_id}`
2. 신규 4개 최소 응답 스펙 구현
- `GET /api/v1/dashboard/map-latest`
- `GET /api/v1/dashboard/big-matches`
- `GET /api/v1/regions/{region_code}/elections`
- `GET /api/v1/matchups/{matchup_id}`
3. 실DB 응답 확인 완료(로컬 PostgreSQL 연결 상태)

### E. 보안 D0 실행(키 회전은 오너 수행)
부분 완료.
1. 완료:
- 키 회전 체크리스트 문서화 완료
- 노출 금지 규칙 문서 반영(`.env`, `supabase_info.txt`, 로그)
2. 오너 수행 필요:
- Supabase Dashboard에서 `service_role` 실제 rotate
- 기존 키 폐기 확인 및 Secret 재주입

## 2) 주요 코드 변경
1. 백엔드
- `app/api/routes.py`: 신규 4개 API 추가
- `app/models/schemas.py`: 신규 응답 모델 추가
- `app/services/repository.py`: map/big-match/region-elections/matchup 쿼리 추가
- `app/services/ingest_service.py`: `matchups` upsert 및 election_id 추론 추가
- `db/schema.sql`: `matchups` 테이블/인덱스 추가

2. 수집기
- `src/pipeline/*`: collector, contracts, standards, ingest adapter 구성
- `tests/test_collector_*`, `tests/test_contracts.py`, `tests/test_ingest_adapter.py` 추가

3. 운영 문서
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
- `docs/README.md`

## 3) 검증 커맨드 로그(요약)
1. 환경 재현
- `.venv/bin/pip install -r requirements.txt`
- `.venv/bin/pytest -q` => `19 passed`

2. 실DB 적재 검증
- `.venv/bin/python scripts/init_db.py` => `schema applied`
- `.venv/bin/python -m app.jobs.manual_ingest --input data/sample_ingest.json` (2회)
- SQL 카운트 검증: 중복 없음 확인

3. API 실DB 검증
- Uvicorn 실행 후 curl로 7개 API 호출
- 기존 3개 + 신규 4개 모두 JSON 응답 확인

## 4) 잔여 리스크 및 요청 의사결정
1. Supabase 운영 키 회전 일정 확정 필요
- 제안: `2026-02-19` 내 rotate 완료

2. 실DB 기준 해석 확인 필요
- 본 보고서의 실DB 검증은 "로컬 PostgreSQL 16" 기준으로 완료
- Supabase 원격 DB 기준으로도 동일 검증이 필요하면, 오너가 `DATABASE_URL` 제공 후 동일 시나리오 재실행 필요

## 5) 다음 액션
1. 문서/보고서 커밋 완료
2. 필요 시 Supabase 원격 DB 재검증(동일 스크립트/커맨드)
3. PR 생성 및 커밋 단위 리뷰 진행

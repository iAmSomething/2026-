# Election 2026 Backend MVP

문서 기반 계획(`docs/`)을 코드로 옮긴 1주차 백엔드 세로슬라이스입니다.

## 포함 기능
- FastAPI 공개 API 7개
  - `GET /api/v1/dashboard/summary`
  - `GET /api/v1/dashboard/map-latest`
  - `GET /api/v1/dashboard/big-matches`
  - `GET /api/v1/regions/search`
  - `GET /api/v1/regions/{region_code}/elections`
  - `GET /api/v1/matchups/{matchup_id}`
  - `GET /api/v1/candidates/{candidate_id}`
- FastAPI 내부 API 1개
  - `POST /api/v1/jobs/run-ingest` (Bearer 토큰 인증)
- PostgreSQL 스키마 (`db/schema.sql`)
- 수동 적재 CLI (`python -m app.jobs.manual_ingest --input data/sample_ingest.json`)
- 정규화 로직 (`53~55%` -> min/max/mid)
- 테스트(정규화, 적재 idempotent, API 계약)

## 빠른 시작
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env에 DATABASE_URL/SUPABASE 키 입력
python scripts/init_db.py
python -m app.jobs.manual_ingest --input data/sample_ingest.json
uvicorn app.main:app --reload
```

## 런타임 주의
- Python `3.13` 사용 권장 (`3.14`에서는 `pydantic-core` 빌드 실패 가능)

## 보안
- `key.txt`, `supabase_info.txt`, `.env*`는 커밋 금지
- 서비스 키는 로컬 파일이 아닌 배포 Secret으로 주입
- Supabase `service_role` 키는 노출 이력 발생 시 즉시 rotate 후 재주입
- 내부 실행 API는 `INTERNAL_JOB_TOKEN`으로 보호

## QA
- 로컬 Phase1 체크: `scripts/qa/check_phase1.sh`
- DB 포함 체크: `scripts/qa/check_phase1.sh --with-db`
- API 포함 체크: `scripts/qa/check_phase1.sh --with-api`

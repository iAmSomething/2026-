# Election 2026 Backend MVP

문서 기반 계획(`docs/`)을 코드로 옮긴 1주차 백엔드 세로슬라이스입니다.

## 포함 기능
- FastAPI 공개 API 11개
  - `GET /api/v1/ops/metrics/summary` (운영 지표)
  - `GET /api/v1/review-queue/items`
  - `GET /api/v1/review-queue/stats`
  - `GET /api/v1/review-queue/trends`
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
- 부트스트랩 배치 적재 CLI (`python -m app.jobs.bootstrap_ingest --input <file|dir> --report <json>`)
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

## 배치 부트스트랩 실행기
```bash
# 단일 파일 실행
python -m app.jobs.bootstrap_ingest \
  --input data/bootstrap_ingest_batch_2.json \
  --report data/bootstrap_ingest_batch_2_report.json

# 디렉토리 실행 (패턴 기본값: *.json)
python -m app.jobs.bootstrap_ingest \
  --input data/bootstrap_batches \
  --pattern "*.json" \
  --report data/bootstrap_ingest_dir_report.json
```
- 요약 리포트 필수 필드: `total`, `success`, `fail`, `review_queue_count`

## 런타임 주의
- Python `3.13` 사용 권장 (`3.14`에서는 `pydantic-core` 빌드 실패 가능)

## 보안
- `key.txt`, `supabase_info.txt`, `.env*`는 커밋 금지
- 서비스 키는 로컬 파일이 아닌 배포 Secret으로 주입
- Supabase `service_role` 키는 노출 이력 발생 시 즉시 rotate 후 재주입
- 내부 실행 API는 `INTERNAL_JOB_TOKEN`으로 보호

## GitHub Secrets (CI 필수)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATA_GO_KR_KEY`
- `DATABASE_URL`
- `INTERNAL_JOB_TOKEN`
- Preflight 스크립트: `scripts/qa/preflight_required_secrets.sh`
- Preflight 적용 워크플로:
  - `.github/workflows/phase1-qa.yml`
  - `.github/workflows/ingest-schedule.yml`
  - `.github/workflows/staging-smoke.yml` (DB는 서비스 postgres fallback 허용)

## QA
- 로컬 Phase1 체크: `scripts/qa/check_phase1.sh`
- DB 포함 체크: `scripts/qa/check_phase1.sh --with-db`
- API 포함 체크: `scripts/qa/check_phase1.sh --with-api`
- API 11종 계약 스위트: `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report.json`
- 스테이징 스모크(로컬 URL 기준): `API_BASE=http://127.0.0.1:8100 WEB_BASE=http://127.0.0.1:3300 INTERNAL_JOB_TOKEN=<token> scripts/qa/smoke_staging.sh`
- 스테이징 웹 앱(개발 트랙): `apps/staging-web`
- 스테이징 CI 워크플로: `.github/workflows/staging-smoke.yml`
- DB 동등성 자동검증(로컬): `DATABASE_URL=<dsn> .venv/bin/python scripts/qa/run_db_equivalence.py --target local --report data/qa_local_db_report.json`
- DB 동등성 자동검증(원격): `REMOTE_DATABASE_URL=<dsn> .venv/bin/python scripts/qa/run_db_equivalence.py --target remote --report data/qa_remote_db_report.json`
- 내부 API 배치 재시도 실행: `INTERNAL_JOB_TOKEN=<token> .venv/bin/python scripts/qa/run_ingest_with_retry.py --api-base http://127.0.0.1:8100 --input data/sample_ingest.json --report data/ingest_schedule_report.json`
- QA 보고서 경로: `QA_reports/`
- QA 보고서 파일명: `YYYY-MM-DD_qa_<topic>_report.md`
- 리포트 스캔(4개 트랙): `bash scripts/pm/report_scan.sh`

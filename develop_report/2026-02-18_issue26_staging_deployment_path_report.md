# 2026-02-18 Issue #26 Staging Deployment Path Report

## 1) 범위
- 이슈: `#26 [DEVELOP] 스테이징 배포 경로 구축(FastAPI+Next+Supabase)`
- 목표: FastAPI + Supabase + Next.js 최소 스테이징 경로 구축 및 스모크 검증

## 2) 구현 사항
1. 스테이징 스모크 워크플로 추가
- 파일: `.github/workflows/staging-smoke.yml`
- 기능:
  - Python 3.13 / Node 20 셋업
  - DB schema 적용 + 샘플 적재
  - API(8100) + Web(3300) 기동
  - `scripts/qa/smoke_staging.sh` 실행
  - API/Web 로그 아티팩트 업로드

2. 스테이징 스모크 스크립트 추가
- 파일: `scripts/qa/smoke_staging.sh`
- 검증:
  - `GET /health`
  - `POST /api/v1/jobs/run-ingest` (Bearer)
  - `GET /api/v1/dashboard/summary`
  - `GET /api/v1/regions/search`
  - `GET /api/v1/candidates/{candidate_id}`
  - `GET /` (Web)
  - 로그 내 민감패턴(`sb_secret_`, `SUPABASE_SERVICE_ROLE_KEY=`, `INTERNAL_JOB_TOKEN=`) 탐지 시 실패 처리

3. 개발 트랙용 최소 Next 스테이징 앱 추가
- 경로: `apps/staging-web`
- 파일:
  - `apps/staging-web/package.json`
  - `apps/staging-web/package-lock.json`
  - `apps/staging-web/next.config.mjs`
  - `apps/staging-web/app/layout.js`
  - `apps/staging-web/app/page.js`
- 역할: API summary 연동 상태를 최소 UI로 표시

4. 실행 안정화 보완
- 파일: `scripts/init_db.py`
- 변경: `PYTHONPATH` 없이도 루트 기준으로 `app` import 가능하도록 경로 보강

5. 문서/가이드 업데이트
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- `README.md`
- `.env.example`
- `.gitignore`

## 3) 로컬 검증 결과
- 스테이징 URL(로컬): `http://127.0.0.1:3300`
- API URL(로컬): `http://127.0.0.1:8100`

실행 결과:
- `pytest`: `33 passed`
- `npm --prefix apps/staging-web run build`: 성공
- `scripts/qa/smoke_staging.sh`: 성공

스모크 핵심 출력:
- `summary_ok 0 1`
- `regions_ok 1`
- `candidate_ok cand-jwo`
- `web_ok`
- `secret masking in logs` 통과

## 4) 완료기준 매핑
1. 스테이징 URL 1개 공유
- 충족: `http://127.0.0.1:3300`

2. API smoke test 결과 첨부
- 충족: `scripts/qa/smoke_staging.sh` 통과 결과 기록

3. 민감정보 노출 0건 확인
- 충족: 로그 패턴 스캔 통과

## 5) 의사결정 필요 사항
1. 외부 스테이징 URL 전환 여부
- 현재는 로컬/CI 루프백 URL(`127.0.0.1`) 기준 검증 경로입니다.
- Vercel/Railway 외부 스테이징 URL을 운영 기준으로 확정할지 결정 필요.

2. UIUX 앱 통합 시점
- develop 전용 최소 앱(`apps/staging-web`)을 추가했습니다.
- 추후 UIUX 본 앱(`apps/web`)과 통합할 기준/시점 결정 필요.

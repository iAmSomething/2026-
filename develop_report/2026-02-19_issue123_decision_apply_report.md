# 2026-02-19 Issue #123 Decision Apply Report

## 1. 목적
- 오너 확정사항 즉시 반영:
  1. `NEXT_PUBLIC_API_BASE_URL` 운영 고정값 `https://2026-api.up.railway.app`
  2. Preview URL 접근정책 `public`
  3. API CORS에 `https://2026-deploy.vercel.app` 허용
  4. 내부 운영 API 토큰 정책 유지

## 2. 반영 파일
1. `app/main.py`
2. `apps/staging-web/app/page.js`
3. `.github/workflows/vercel-preview.yml`
4. `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
5. `docs/05_RUNBOOK_AND_OPERATIONS.md`
6. `tests/test_api_routes.py`
7. `develop_report/2026-02-19_issue123_decision_apply_report.md`

## 3. 구현 상세
1. FastAPI CORS 설정 추가
- `app/main.py`에 `CORSMiddleware` 적용
- 기본 허용 오리진에 `https://2026-deploy.vercel.app` 포함
- 환경변수 `CORS_ALLOW_ORIGINS`(comma-separated)로 오버라이드 가능

2. 웹 API base 기본값 고정
- `apps/staging-web/app/page.js` 기본 API base를 `https://2026-api.up.railway.app`로 변경

3. Vercel Preview CI 정책 반영
- `.github/workflows/vercel-preview.yml`에 `WEB_API_BASE_URL=https://2026-api.up.railway.app` 고정
- build/deploy 시 `API_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`를 동일 값으로 주입
- 접근검증에서 `401(auth_gated)` 허용 제거, `public(2xx/3xx)`만 성공 처리

4. 문서 반영
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
  - CORS 허용 오리진 고정값, preview `public` 정책, API base 고정값 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - RC 체크리스트 API_BASE 기본값을 Railway URL로 고정
  - 내부 운영 API 토큰 정책 유지 명시

5. 내부 운영 API 토큰 정책
- `/api/v1/jobs/run-ingest`의 `Authorization: Bearer <INTERNAL_JOB_TOKEN>` 검증 로직 유지

## 4. 검증
1. Python 테스트
```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q tests/test_api_routes.py -k "run_ingest_requires_bearer_token or cors"
```
- 결과: `3 passed, 5 deselected`

2. Staging Web 빌드
```bash
npm --prefix apps/staging-web ci
npm --prefix apps/staging-web run build
```
- 결과: build 성공

## 5. 비고
1. Production Vercel 환경변수는 프로젝트 설정값이 우선이며, 이번 반영은 CI deploy 주입 + 앱 기본값으로 동작 안정성을 확보했다.
2. 오너가 Vercel 프로젝트(Preview/Production) UI에도 동일 값으로 고정한 상태를 유지하면 운영 일관성이 최대화된다.

# 2026-02-20 Issue #129 Railway API Go-Live Report

## 1. 목적
- `https://2026-api.up.railway.app` 실배포 상태를 실측하고, #125 재게이트용 검증 근거를 제출한다.

## 2. 반영 파일
1. `scripts/qa/smoke_public_api.sh`
2. `docs/05_RUNBOOK_AND_OPERATIONS.md`
3. `develop_report/2026-02-20_issue127_railway_api_go_live_report.md`

## 3. 검증 명령
```bash
scripts/qa/smoke_public_api.sh \
  --api-base "https://2026-api.up.railway.app" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/issue129_public_api
```

## 4. 실측 결과 (2026-02-20 UTC)
1. 엔드포인트 상태코드
- `GET /health` -> `404`
- `GET /api/v1/dashboard/summary` -> `404`
- `GET /api/v1/regions/search?query=서울` -> `404`
- `GET /api/v1/candidates/cand-jwo` -> `404`
- `OPTIONS /api/v1/dashboard/summary` (CORS preflight) -> `404`

2. 샘플 응답 본문
```json
{"status":"error","code":404,"message":"Application not found"}
```

3. 판정
- 현재 도메인은 FastAPI 앱 응답이 아니라 Railway 플랫폼 레벨 `Application not found` 상태로 확인됨.
- 따라서 #129 수용 기준(실측 200 + CORS 확인)은 **미충족(Blocked)**.

## 5. 개발 측 완료 항목
1. 원격 공개 API 스모크 자동화 스크립트 추가 (`scripts/qa/smoke_public_api.sh`)
2. 런북에 원격 스모크 절차 추가 (`docs/05_RUNBOOK_AND_OPERATIONS.md` 15절)
3. 실패 원인 및 실측 로그를 보고서로 고정

## 6. 오너 액션 필요 (외부 인프라)
1. Railway에서 `2026-api.up.railway.app` 도메인에 FastAPI 서비스를 실제 연결/배포
2. Railway 서비스 환경변수 주입:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATA_GO_KR_KEY`
- `DATABASE_URL`
- `INTERNAL_JOB_TOKEN`
3. 배포 후 아래 재실행으로 수용 기준 검증:
```bash
scripts/qa/smoke_public_api.sh \
  --api-base "https://2026-api.up.railway.app" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/issue129_public_api
```

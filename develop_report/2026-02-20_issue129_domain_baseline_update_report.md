# 2026-02-20 Issue #129 Domain Baseline Update Report

## 1. 목적
- Railway 실운영 API 기준 도메인을 실제 응답 가능한 값으로 고정하고, web/CI/runbook 기본값을 동기화한다.

## 2. 배경
1. 기존 이슈 기준값: `https://2026-api.up.railway.app`
2. 실측 결과: 위 도메인은 `404 Application not found`
3. 실제 배포 서비스 도메인: `https://2026-api-production.up.railway.app`
4. Railway 정책상 `*.up.railway.app`은 Custom Domain으로 직접 지정 불가하여, 생성 도메인을 운영 기준으로 사용

## 3. 반영 파일
1. `.github/workflows/vercel-preview.yml`
2. `apps/web/app/_lib/api.js`
3. `apps/staging-web/app/page.js`
4. `scripts/qa/smoke_public_api.sh`
5. `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
6. `docs/05_RUNBOOK_AND_OPERATIONS.md`
7. `develop_report/2026-02-20_issue129_domain_baseline_update_report.md`

## 4. 변경 내용
1. 공개/프리뷰 API 기본값을 `https://2026-api-production.up.railway.app`로 통일
2. 웹 fallback 해석 우선순위는 기존 유지
- `API_BASE_URL` -> `NEXT_PUBLIC_API_BASE_URL` -> 고정 기본값
3. 공개 API 스모크 스크립트 기본 타깃 도메인 교체
4. 배포/운영 런북 예시 명령의 API base 교체

## 5. 실측 결과 (UTC)
### 5.1 API 스모크
```bash
scripts/qa/smoke_public_api.sh \
  --api-base "https://2026-api-production.up.railway.app" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/public_api_smoke_issue129
```

결과:
- `health=200`
- `summary=200`
- `regions=200`
- `candidate=200`
- `cors=200`
- `cors_allow_origin=https://2026-deploy.vercel.app`
- 판정: `PASS`

샘플 body:
- `/health` -> `{"status":"ok"}`
- `/api/v1/dashboard/summary` -> `{"as_of":null,"party_support":[],...}`
- `/api/v1/regions/search?q=서울` -> `[ {"region_code":"11-000",...} ]`
- `/api/v1/candidates/cand-jwo` -> `{"candidate_id":"cand-jwo",...}`

### 5.2 웹 라우트 RC
```bash
curl -sS -o /tmp/issue129_web_home.html -w "web_home %{http_code}\n" "https://2026-deploy.vercel.app/"
curl -sS -o /tmp/issue129_web_matchup.html -w "web_matchup %{http_code}\n" "https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor"
curl -sS -o /tmp/issue129_web_candidate.html -w "web_candidate %{http_code}\n" "https://2026-deploy.vercel.app/candidates/cand-jwo"
```

결과:
- `web_home 200`
- `web_matchup 200`
- `web_candidate 200`

### 5.3 기존 고정값 도메인 상태
```bash
curl -sS -o /tmp/issue129_old_domain_health.txt -w "old_health %{http_code}\n" "https://2026-api.up.railway.app/health"
```

결과:
- `old_health 404`
- body: `{"status":"error","code":404,"message":"Application not found",...}`

## 6. 결론
- 실서비스 기준에서 #129의 배포/CORS/헬스체크 요구사항은 충족되었다.
- 다만 도메인은 이슈 본문의 `2026-api.up.railway.app` 대신, 실제 동작 도메인 `2026-api-production.up.railway.app`을 운영 기준으로 확정해야 한다.

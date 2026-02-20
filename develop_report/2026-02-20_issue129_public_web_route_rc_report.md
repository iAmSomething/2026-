# 2026-02-20 Issue #131 Public Web Route RC Report

## 1. 목적
- 공개 웹 RC를 홈 전용에서 라우트 포함(`/`, `/matchups/:id`, `/candidates/:id`) 형태로 승격 가능 상태로 main에 반영한다.

## 2. 반영 파일
1. `apps/web/package.json`
2. `apps/web/package-lock.json`
3. `apps/web/next.config.mjs`
4. `apps/web/app/layout.js`
5. `apps/web/app/_lib/api.js`
6. `apps/web/app/page.js`
7. `apps/web/app/matchups/[matchup_id]/page.js`
8. `apps/web/app/candidates/[candidate_id]/page.js`
9. `.github/workflows/vercel-preview.yml`
10. `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
11. `docs/05_RUNBOOK_AND_OPERATIONS.md`
12. `develop_report/2026-02-20_issue129_public_web_route_rc_report.md`

## 3. 구현 내용
1. `apps/web`를 독립 Next.js 앱으로 스캐폴드
- 홈(`/`)
- 매치업(`/matchups/[matchup_id]`)
- 후보(`/candidates/[candidate_id]`)

2. API base 고정값 유지
- 기본값: `https://2026-api.up.railway.app`
- 우선순위: `API_BASE_URL` -> `NEXT_PUBLIC_API_BASE_URL` -> 기본값

3. Vercel preview dispatch 기본값 전환
- `.github/workflows/vercel-preview.yml`의 `root_dir` 기본값을 `apps/web`로 변경

4. 런북/배포 문서 동기화
- 공개 라우트 RC 체크 기준 3개 URL 명시

## 4. 로컬 검증 (성공)
1. 빌드
```bash
npm --prefix apps/web install
npm --prefix apps/web run build
```
2. 로컬 기동/확인
```bash
PORT=3311 API_BASE_URL="https://2026-api.up.railway.app" NEXT_PUBLIC_API_BASE_URL="https://2026-api.up.railway.app" npm --prefix apps/web run start
curl -sS -o /tmp/issue131_home.html -w "home %{http_code}\n" http://127.0.0.1:3311/
curl -sS -o /tmp/issue131_matchup.html -w "matchup %{http_code}\n" http://127.0.0.1:3311/matchups/m_2026_seoul_mayor
curl -sS -o /tmp/issue131_candidate.html -w "candidate %{http_code}\n" http://127.0.0.1:3311/candidates/cand-jwo
```
3. 결과
- `home 200`
- `matchup 200`
- `candidate 200`

## 5. 공개 도메인 실측 (현재)
```bash
curl -sS -o /tmp/issue131_public_home.html -w "home %{http_code}\n" https://2026-deploy.vercel.app/
curl -sS -o /tmp/issue131_public_matchup.html -w "matchup %{http_code}\n" https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor
curl -sS -o /tmp/issue131_public_candidate.html -w "candidate %{http_code}\n" https://2026-deploy.vercel.app/candidates/cand-jwo
```

- `home 200`
- `matchup 404`
- `candidate 404`

판정:
- 현재 공개 도메인은 여전히 `apps/staging-web` 기준 응답으로 확인되며, 라우트 2개가 404다.
- 따라서 수용 기준의 “공개 3 URL 200”은 미충족이며, Vercel 프로젝트 루트 전환/배포가 필요하다.

## 6. 오너 액션 필요 (외부 설정)
1. Vercel 프로젝트 Root Directory를 `apps/web`로 전환
2. Production 재배포
3. 아래 재검증 후 #125 재게이트:
```bash
for u in \
  "https://2026-deploy.vercel.app/" \
  "https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor" \
  "https://2026-deploy.vercel.app/candidates/cand-jwo"; do
  curl -sS -o /tmp/$(echo "$u" | tr '/:.' '_').html -w "$u -> %{http_code}\n" "$u"
done
```

# 2026-02-19 Issue #123 Web RC Lock Report

## 1. 목적
- Issue #123 `[DEVELOP] 웹 확인용 RC 고정(공개 URL/API env/런북)` 대응
- 공개 확인 URL/브랜치/배포설정 고정 문서화, API env 확인, RC 체크리스트(runbook) 작성

## 2. 반영 파일
1. `.github/workflows/vercel-preview.yml`
2. `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
3. `docs/05_RUNBOOK_AND_OPERATIONS.md`
4. `develop_report/2026-02-19_issue123_web_rc_lock_report.md`

## 3. 구현 내용
1. Vercel Preview dispatch 입력 고정
- `root_dir` 선택지를 `apps/staging-web` 단일값으로 고정
- `issue_number`는 실행 시 명시 입력(기본값 제거)

2. 배포/환경 문서 고정
- 공개 확인 URL: `https://2026-deploy.vercel.app`
- 배포 기준 브랜치: `main` (Production deployment ref 기준)
- 웹 API env 우선순위(`API_BASE_URL -> NEXT_PUBLIC_API_BASE_URL -> 127.0.0.1`) 명시
- 스테이징/공개 환경에서 env 누락 시 fallback(`summary fetch failed`) 동작 명시

3. RC 런북 체크리스트 추가
- URL 접근(200) 확인
- 핵심 API 3개(`/dashboard/summary`, `/regions/search`, `/candidates/{id}`) 확인 명령
- 빈데이터/오류 fallback 확인 절차 추가

## 4. 검증 기록 (2026-02-19 UTC)
1. 공개 URL 접근 확인
```bash
curl -sS -o /tmp/issue123_web_home.html -w "HOME_STATUS=%{http_code}\n" "https://2026-deploy.vercel.app"
```
- 결과: `HOME_STATUS=200`

2. 공개 웹 도메인에서 API 경로 응답 확인
```bash
curl -sS -o /tmp/issue123_api_dashboard.json -w "%{http_code}\n" "https://2026-deploy.vercel.app/api/v1/dashboard/summary"
curl -sS -o /tmp/issue123_api_regions.json -w "%{http_code}\n" "https://2026-deploy.vercel.app/api/v1/regions/search?query=%EC%84%9C%EC%9A%B8"
curl -sS -o /tmp/issue123_api_candidate.json -w "%{http_code}\n" "https://2026-deploy.vercel.app/api/v1/candidates/cand-jwo"
```
- 결과: 3개 모두 `404` (웹 도메인 자체 API 미제공 상태)

3. 홈 fallback 렌더 확인
```bash
rg -n "Election 2026 Staging|API Base|summary fetch failed" /tmp/issue123_web_home.html
```
- 결과:
  - `Election 2026 Staging` 노출 확인
  - `API Base: http://127.0.0.1:8100` 노출 확인
  - `summary fetch failed: fetch failed` 노출 확인

4. Production deployment ref 확인
```bash
gh api "repos/iAmSomething/2026-/deployments?per_page=100" --jq '[.[] | select(.environment=="Production")][0] | {ref,created_at,environment}'
git branch -r --contains b32e774ea9936570364a35bcd0d584603011407b
```
- 결과:
  - Production ref: `b32e774ea9936570364a35bcd0d584603011407b`
  - 포함 브랜치: `origin/main`

## 5. 수용 기준 판정
1. 공개 URL 접근 200 확인: `PASS`
2. RC 런북 보고서 제출: `PASS`
3. 재현 명령/링크 포함: `PASS`

## 6. 의사결정 필요사항
1. 스테이징/공개 웹에서 실제 API 연동 성공 상태를 보여주기 위해 Vercel 환경변수 `NEXT_PUBLIC_API_BASE_URL` 고정값을 어떤 URL로 운영할지 확정 필요
2. preview URL의 접근 정책(`public` vs `auth_gated`)을 운영 기본값으로 확정 필요

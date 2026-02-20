# 2026-02-20 Issue #131 Public Web Route RC Pass Report

## 1. 목적
- 공개 웹 RC 라우트 승격 이슈(#131)의 최종 수용 기준(3개 URL 200) 충족 여부를 실측으로 확정한다.

## 2. 실측 명령
```bash
curl -sS -o /tmp/final_home.html -w "web_home %{http_code}\n" "https://2026-deploy.vercel.app/"
curl -sS -o /tmp/final_matchup.html -w "web_matchup %{http_code}\n" "https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor"
curl -sS -o /tmp/final_candidate.html -w "web_candidate %{http_code}\n" "https://2026-deploy.vercel.app/candidates/cand-jwo"
```

## 3. 실측 결과 (UTC)
1. `https://2026-deploy.vercel.app/` -> `200`
2. `https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor` -> `200`
3. `https://2026-deploy.vercel.app/candidates/cand-jwo` -> `200`

## 4. API base 동작 확인
1. 홈 렌더에 `API Base: https://2026-production.up.railway.app` 노출 확인
2. 후보 라우트에서 `api_status: 200` 확인
3. 매치업 라우트는 `api_status: 404`(`matchup not found`)이지만, 페이지 자체 라우트 응답은 `200`으로 수용 기준 충족

## 5. 결론
- 이슈 #131 수용 기준(공개 3 URL 200)은 충족되어 close 가능 상태다.

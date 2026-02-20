# 2026-02-20 Issue #139 Matchup ID Alignment Report

## 1. 목적
- 공개 웹 라우트 `/matchups/m_2026_seoul_mayor`와 백엔드 `matchup_id`를 정합화하여 페이지 내부 `api_status`를 200으로 만든다.

## 2. 원인 진단
1. 공개 웹 라우트는 `m_2026_seoul_mayor`를 사용
2. 실제 API 데이터 식별자는 `20260603|광역자치단체장|11-000`
3. 실측 기준 기존 alias 호출은 404
```bash
curl -sS -o /tmp/issue140_matchup_alias.json -w "%{http_code}\n" \
  "https://2026-api-production.up.railway.app/api/v1/matchups/m_2026_seoul_mayor"
# 404
```

## 3. 구현
1. 서버 alias 매핑(B안) 적용
- `app/api/routes.py`
- `MATCHUP_ID_ALIASES["m_2026_seoul_mayor"] = "20260603|광역자치단체장|11-000"`
- `/api/v1/matchups/{matchup_id}` 진입 시 alias를 canonical id로 resolve 후 조회

2. 테스트 보강
- `tests/test_api_routes.py`
- `/api/v1/matchups/m_2026_seoul_mayor` 호출 시 200 + canonical `matchup_id` 반환 검증 추가

3. 운영 문서 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 공개 웹 매치업 RC 라우트가 alias -> canonical로 조회된다는 운영 노트 추가

## 4. 로컬 검증
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_api_routes.py
```
결과:
- `8 passed`

## 5. 공개 환경 재검증 절차(머지 후)
1. API alias 응답 확인
```bash
curl -sS -o /tmp/issue140_post_alias.json -w "api_alias %{http_code}\n" \
  "https://2026-api-production.up.railway.app/api/v1/matchups/m_2026_seoul_mayor"
```
2. 웹 라우트 확인
```bash
curl -sS -o /tmp/issue140_post_matchup.html -w "web_matchup %{http_code}\n" \
  "https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor"
rg -n "api_status" /tmp/issue140_post_matchup.html
```
3. 수용 기준 판정
- `api_alias 200`
- `web_matchup 200`
- 웹 HTML에 `api_status: 200` 표기

## 6. 결론
- alias 매핑을 서버에 추가해 공개 URL과 실제 데이터 식별자 간 불일치를 제거했다.

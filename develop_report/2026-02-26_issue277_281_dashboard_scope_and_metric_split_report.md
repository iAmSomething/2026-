# 2026-02-26 DEVELOP P0 대시보드 스코프 오염 차단/지표 분리 보고서 (#277, #281)

## 1) 작업 범위
1. #277 `[DEVELOP][P0] 전국 카드 스코프 오염 차단`
2. #281 `[DEVELOP][P0] 대통령 지지율 vs 선거 성격 지표 분리`

## 2) 핵심 변경
1. `GET /api/v1/dashboard/summary` 응답 계약 확장:
   - `party_support`
   - `president_job_approval` (신규)
   - `election_frame` (신규)
   - `presidential_approval` (deprecated, 하위호환)
   - `presidential_approval_deprecated=true`
2. summary 집계는 기존대로 `audience_scope='national'`만 카드 목록에 포함(지역/기초 스코프 차단 유지).
3. `presidential_approval` 옵션을 API에서 분류:
   - 대통령 직무평가 버킷: `긍정/부정/직무/국정수행` 계열
   - 선거 성격 버킷: `국정안정/국정견제/안정론/견제론/정권교체` 계열
4. 웹 대시보드 카드 분리:
   - `대통령 직무평가` 카드(긍정/부정)
   - `선거 성격` 카드(안정/견제)
5. fallback fixture(`apps/web/public/mock_fixtures_v0.2/dashboard_summary.json`)를 신규 계약으로 갱신.

## 3) 변경 파일
1. `app/models/schemas.py`
2. `app/api/routes.py`
3. `apps/web/app/page.js`
4. `apps/web/public/mock_fixtures_v0.2/dashboard_summary.json`
5. `tests/test_api_routes.py`
6. `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
7. `docs/03_UI_UX_SPEC.md`

## 4) 검증
1. 실행:
```bash
SUPABASE_URL=https://example.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=test \
DATA_GO_KR_KEY=test \
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/app \
/Users/gimtaehun/election2026_codex/.venv/bin/pytest
```
2. 결과: `159 passed`.

## 5) 완료 기준 대비
1. 전국 카드에 지역 스코프 혼입 차단: 유지/검증 완료.
2. 대통령 지지율 카드에서 `국정안정론/국정견제론` 분리: 완료.
3. 선거 성격 카드 별도 노출: 완료.
4. API/프론트 회귀 테스트 green: 완료.

## 6) 의사결정 필요
1. `presidential_approval` deprecated 필드 제거 시점(릴리스 버전/날짜) 확정 필요.
2. 분류 키워드 taxonomy를 collector와 단일 사전으로 승격할지 여부 확정 필요(현재는 API 계층 규칙).

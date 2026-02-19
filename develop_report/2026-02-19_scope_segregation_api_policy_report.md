# 2026-02-19 Scope Segregation API Policy Report

## 1. 작업 목표
- Issue: #107 `[DEVELOP] 스코프 분리 집계정책 강화(전국 오염 방지)`
- 목표:
  1. `dashboard summary`에 전국 스코프 강제 반영
  2. `summary/map/big-matches`에 `audience_scope` 및 `scope_breakdown` 노출
  3. 스코프 오염 회귀 테스트 추가

## 2. 구현 내용
1. 응답 계약 확장 (`app/models/schemas.py`)
- `SummaryPoint`, `MapLatestPoint`, `BigMatchPoint`에 `audience_scope` 추가
- `ScopeBreakdownOut` 모델 추가 (`national/regional/local/unknown`)
- `DashboardSummaryOut`, `DashboardMapLatestOut`, `DashboardBigMatchesOut`에 `scope_breakdown` 추가

2. 집계 정책 강제 (`app/services/repository.py`, `app/api/routes.py`)
- `fetch_dashboard_summary` SQL 필터를 `o.audience_scope = 'national'`로 강화
- `audience_scope IS NULL` 임시 포함 제거
- API 라우트에서 summary 처리 시 `audience_scope='national'`만 결과 배열에 반영(이중 방어)
- map/big-matches 조회 결과에 `audience_scope` 포함
- summary/map/big-matches 응답에 `scope_breakdown` 계산/노출

3. 회귀 방지 테스트 (`tests/test_api_routes.py`, `tests/test_repository_dashboard_summary_scope.py`)
- summary 오염 데이터(regional/local)가 repo에서 들어와도 응답 결과는 national-only 유지 검증
- `scope_breakdown`이 스코프별 카운트를 노출하는지 검증
- repository query에 national-only 필터가 적용되고 `audience_scope IS NULL`이 제거됐는지 검증

4. 문서/운영 업데이트
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - summary 스코프 규칙에서 `audience_scope IS NULL` 제외로 업데이트
  - dashboard 3개 API의 `scope_breakdown` 노출 규칙 추가
- `docs/03_UI_UX_SPEC.md`
  - summary/map/big-matches 필수 필드에 `audience_scope`, `scope_breakdown` 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 운영 일일 체크에 `scope_breakdown.regional/local/unknown == 0` 확인 항목 추가

5. 샘플 응답 추가
- `data/scope_segregation_dashboard_samples_v1.json`

## 3. 검증
1. 타깃 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_repository_dashboard_summary_scope.py`
- 결과: `8 passed`

2. 전체 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `69 passed`

## 4. DoD 점검
1. API 계약/회귀 테스트 PASS: 완료
2. 샘플 응답 + 문서 업데이트: 완료
3. 보고서 제출: 완료

## 5. 산출물
- `develop_report/2026-02-19_scope_segregation_api_policy_report.md`
- `data/scope_segregation_dashboard_samples_v1.json`

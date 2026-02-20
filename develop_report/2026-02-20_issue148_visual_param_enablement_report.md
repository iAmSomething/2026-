# 2026-02-20 Issue #148 Visual Param Enablement Report

## 1. 목적
- 공개 웹 baseline 파라미터 시나리오(B02~B10)가 실제 UI 상태(카피/배지/패널)로 반영되도록 구현한다.

## 2. 구현 범위
1. Home
- `scope_mix=1` 시 스코프 혼재 경고 배지/카피 노출
- `selected_region=KR-11` 시 `11-000`으로 정규화하여 지역 패널 선택 상태 반영

2. Search
- `demo_query=연수국` 시 alias 보정(`연수구`) 상태 노출
- `demo_query=없는지역명` 시 empty-state + 대체 액션(서울/인천 재검색) 노출

3. Matchup
- `confirm_demo`, `source_demo`, `demo_state` 조합 배지와 상태 카피 노출
- alias 요청 ID와 canonical 표준 ID 병기

4. Candidate
- `party_demo`, `confirm_demo` 상태 배지 노출
- 미존재 후보 ID 요청 시 `cand-jwo` 안전 fallback 렌더(404 내부패널 제거)

## 3. 변경 파일
1. `apps/web/app/page.js`
2. `apps/web/app/search/page.js`
3. `apps/web/app/matchups/[matchup_id]/page.js`
4. `apps/web/app/candidates/[candidate_id]/page.js`
5. `apps/web/app/_components/RegionalMapPanel.js`
6. `apps/web/app/_components/demoParams.js`
7. `apps/web/app/globals.css`
8. `docs/05_RUNBOOK_AND_OPERATIONS.md`
9. `develop_report/2026-02-20_issue148_visual_param_enablement_report.md`

## 4. 로컬 검증
1. 빌드
```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
```
결과: 성공

2. baseline 시나리오 URL(로컬)
- B02: `/?scope_mix=1`
- B03: `/?selected_region=KR-11`
- B04: `/search?demo_query=%EC%97%B0%EC%88%98%EA%B5%AD`
- B05: `/search?demo_query=%EC%97%86%EB%8A%94%EC%A7%80%EC%97%AD%EB%AA%85`
- B06: `/matchups/m_2026_seoul_mayor?confirm_demo=article&source_demo=article&demo_state=ready`
- B07: `/matchups/m_2026_seoul_mayor?confirm_demo=official&source_demo=nesdc&demo_state=ready`
- B08: `/candidates/cand-jwo?party_demo=inferred&confirm_demo=article`
- B09: `/candidates/cand-jwo?party_demo=official&confirm_demo=official`
- B10: `/candidates/cand-does-not-exist?party_demo=inferred&confirm_demo=official`

3. 로컬 실측 결과
- B02~B10 모두 `200`
- B10에서 `candidate not found`/`status: 404` 패널 미노출
- 기본 라우트(`/`, `/search`, `/matchups/m_2026_seoul_mayor`, `/candidates/cand-jwo`) 모두 `200` + RC 임시문구 미노출

## 5. 공개 환경 확인 포인트(머지 후)
1. `https://2026-deploy.vercel.app`에 동일 B02~B10 URL 적용
2. 각 URL에서 아래 상태 노출 확인
- Home: `scope_mix=1`, `selected_region=KR-11 -> 11-000`
- Search: `baseline demo_query 적용`, `자동 보정`, `대체 액션`
- Matchup: `confirm_demo=...`, `source_demo=...`, `demo_state=ready`
- Candidate: `party_demo=...`, `confirm_demo=...`, `baseline 안전 fallback 적용`

## 6. 결론
- baseline 파라미터 시나리오(B02~B10)를 공개 웹 UI 상태로 반영했고, 기존 공개 라우트 회귀 없이 유지했다.

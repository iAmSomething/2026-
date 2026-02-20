# 2026-02-20 Issue #152 Tier B 하드게이트 수정 보고서

## 1. 작업 개요
- 이슈: `#152 [DEVELOP] Tier B 하드게이트 실패(D04~D07) 수정`
- 목표: Tier B 실패 항목(D04~D07)의 기대 카피/배지 노출을 보장하고 QA 하드게이트 통과 조건을 만족

## 2. 코드 변경
1. `apps/web/app/search/page.js`
- D04 빈결과 대체 액션 라벨을 QA 기대 키워드로 고정
  - `예시 검색어 적용`
  - `최근 업데이트`

2. `apps/web/app/matchups/[matchup_id]/page.js`
- D05/D06 시나리오 배지 추가
  - 기사 시나리오: `기사 기반 추정`
  - 공식 시나리오: `공식확정`
- 시나리오 카피 추가
  - `기사 기반 추정 데이터 기준으로 결과를 노출합니다.`
  - `공식확정 데이터 기준으로 결과를 노출합니다.`

3. `apps/web/app/candidates/[candidate_id]/page.js`
- D07 시나리오 배지/카피 추가
  - 배지: `검수 필요`
  - 배지: `공식확정 대기(48시간)`
  - 카피:
    - `정당 정보 신뢰도가 낮아 검수 필요 상태입니다.`
    - `공식확정 대기(48시간) 상태로 운영 정책상 재확인을 기다립니다.`

## 3. 검증
1. 빌드
- 명령: `npm --prefix apps/web ci`
- 명령: `npm --prefix apps/web run build`
- 결과: 성공

2. Tier B URL 키워드 검증
- D04: `/search?demo_query=없는지역명`
  - 확인: `검색 결과가 없습니다`, `예시 검색어 적용`, `최근 업데이트`
- D05: `/matchups/m_2026_seoul_mayor?confirm_demo=article&demo_state=ready&source_demo=article`
  - 확인: `기사 기반 추정`
- D06: `/matchups/m_2026_seoul_mayor?confirm_demo=official&demo_state=ready&source_demo=nesdc`
  - 확인: `공식확정`
- D07: `/candidates/cand-jwo?party_demo=inferred_low&confirm_demo=pending48`
  - 확인: `검수 필요`, `공식확정 대기(48시간)`

3. Tier A 회귀 스모크
- `/?scope_mix=1`
- `/?selected_region=KR-11`
- `/search?demo_query=연수국`
- `/matchups/m_2026_seoul_mayor?confirm_demo=official&source_demo=nesdc&demo_state=ready`
- `/candidates/cand-jwo?party_demo=inferred_low&confirm_demo=pending48`
- 결과: 전부 HTTP `200`

4. 로그 경로
- `data/verification/issue152_tierb_verification_2026-02-20.log`

## 4. 수용기준 충족 여부
1. D04~D07 키워드 규칙: 충족
2. Tier A 회귀 없음: 충족(스모크 200)
3. 보고서 제출: 충족
4. #146 코멘트 증빙 경로 첨부: PR/머지 후 등록 예정

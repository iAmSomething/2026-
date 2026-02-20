# 2026-02-20 Issue #143 Public UI Promotion Report

## 1. 목적
- 공개 웹을 RC 셸 화면에서 실제 대시보드 화면으로 승격하고, `/`, `/search`, `/matchups/{id}`, `/candidates/{id}` 4개 라우트를 운영 API 기준으로 정착한다.

## 2. 반영 범위
1. 홈(`/`) 실컴포넌트 반영
- 최신 정당/대통령 요약 카드
- 지역 지도 인터랙션(GeoJSON + 지역 선택)
- 빅매치 카드

2. 검색(`/search`) 신규 반영
- 지역 검색 입력
- 검색 결과 목록
- 선거 타입 탭(6종)
- 지역별 선거 링크

3. 매치업/후보 상세 화면 승격
- raw JSON 중심 RC 렌더 제거
- 카드/메타/링크 중심 상세 화면으로 교체

4. 배포 소스 경로 단일화 명시
- Vercel preview workflow `root_dir` 선택값을 `apps/web` 단일로 제한
- 배포 문서에 공개 도메인 소스 경로 단일 기준(`apps/web`) 반영

## 3. 변경 파일
1. `.github/workflows/vercel-preview.yml`
2. `apps/web/app/layout.js`
3. `apps/web/app/globals.css`
4. `apps/web/app/page.js`
5. `apps/web/app/search/page.js`
6. `apps/web/app/matchups/[matchup_id]/page.js`
7. `apps/web/app/candidates/[candidate_id]/page.js`
8. `apps/web/app/_components/RegionalMapPanel.js`
9. `apps/web/app/_components/format.js`
10. `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
11. `develop_report/2026-02-20_issue143_public_ui_promotion_report.md`

## 4. RC 임시 문구 제거
- 제거 대상 문구:
  - `Election 2026 Public Web RC`
  - `Matchup Route RC`
  - `Candidate Route RC`
  - raw count(`party_support count`, `presidential_approval count`) 중심 표기
- 결과: 운영 화면 텍스트/컴포넌트 기준으로 교체 완료

## 5. 로컬 검증
1. 빌드
```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
```
결과: 성공

2. 로컬 라우트 스모크
```bash
PORT=3334 API_BASE_URL="https://2026-api-production.up.railway.app" NEXT_PUBLIC_API_BASE_URL="https://2026-api-production.up.railway.app" npm --prefix apps/web run start -- --port 3334
curl http://127.0.0.1:3334/
curl http://127.0.0.1:3334/search
curl http://127.0.0.1:3334/matchups/m_2026_seoul_mayor
curl http://127.0.0.1:3334/candidates/cand-jwo
```
결과:
- `/` 200
- `/search` 200
- `/matchups/m_2026_seoul_mayor` 200
- `/candidates/cand-jwo` 200

## 6. 운영 반영 후 확인 계획
1. 공개 도메인 4개 라우트 200 확인
2. 홈 위젯(summary/map/big-matches) 렌더 확인
3. QA 이슈 #146에 재게이트 요청 코멘트 전달

## 7. 결론
- 공개 웹은 RC 셸 구조에서 실제 대시보드 구조로 승격되었고, 운영 API base(`https://2026-api-production.up.railway.app`)를 유지한다.

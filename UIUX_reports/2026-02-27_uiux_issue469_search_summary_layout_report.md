# 2026-02-27 UIUX Issue #469 Search Summary Layout Report

## 1) 이슈
- issue: #469 `[W12][UIUX][P2] 지역 검색 결과 요약 바/정렬 개선`
- 목표: 검색 결과 리스트 해석 속도를 높이기 위해 상단 요약 바를 추가하고, 카드 정보 우선순위를 재정렬합니다.

## 2) 구현 요약
1. 검색 결과 요약 바 추가
- 결과 수, 데이터 보유 지역 수, 최신 데이터 날짜를 `search-summary-bar`로 상단 고정 노출
- 리스트를 읽기 전 전체 상태를 즉시 판단할 수 있도록 개선

2. 결과 카드 정보 우선순위 재정렬
- 순서를 `이름/코드 -> 상태 -> 최신 데이터 -> 이동 액션`으로 재배치
- 보조 정보(선거유형 배지, 추가 카운트)는 하단 compact 영역으로 이동

3. 모바일 밀도/간격 보정
- 카드 간격, 패딩, 배지 크기를 모바일에서 축소
- 요약 바를 모바일에서 단일 컬럼으로 전환해 읽기 난이도를 낮춤

## 3) 변경 파일
- `apps/web/app/search/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-27_uiux_issue469_search_summary_layout_report.md`
- `UIUX_reports/screenshots/2026-02-27_issue469_search_summary_desktop.png`
- `UIUX_reports/screenshots/2026-02-27_issue469_search_summary_mobile.png`

## 4) 증빙
- desktop: `UIUX_reports/screenshots/2026-02-27_issue469_search_summary_desktop.png`
- mobile: `UIUX_reports/screenshots/2026-02-27_issue469_search_summary_mobile.png`

## 5) 검증
- `cd apps/web && npm ci`
- `cd apps/web && npm run build` PASS

## 6) 상태 제안
- next_status: `status/in-review`

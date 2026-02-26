# 2026-02-26 UIUX Issue #419 Loading Copy Consistency Report

## 1) 이슈
- issue: #419 `[W9][UIUX][P2] 홈/후보 로딩 상태 카피·정보밀도 일관화`
- 목표: 홈/후보 로딩 상태의 카피 톤과 정보 밀도를 일치시키고, 모바일에서 과도한 공백 체감을 줄입니다.

## 2) 구현 요약
1. 홈 `loading_demo` 상태 추가
- query: `/?loading_demo=1`
- 로딩 문구를 2단계(요약 단계 -> 홈 단계)로 분리
- 각 단계에 보조 배지(현재 단계/점검 항목) 추가

2. 후보 상세 `loading_demo` 상태 추가
- query: `/candidates/{candidate_id}?loading_demo=1`
- 후보 조회/출처 검증 단계 배지 추가
- 후보 화면 전용 스켈레톤 블록(3개) 적용

3. 공통 로딩 스타일 규칙 신설
- `loading-callout`: 고정 톤/카피 밀도
- `skeleton-block` + `shimmer` 애니메이션
- 모바일(<=980px)에서 스켈레톤 높이/간격 축소로 밀도 보정

## 3) 상태 카피 규칙 (고정)
- 홈 1단계: `요약 데이터를 불러오는 중입니다.`
- 홈 2단계: `홈 데이터를 불러오는 중입니다.`
- 후보: `후보 정보를 불러오는 중입니다.`
- 보조 문구는 "현재 확인 중인 작업"(출처/신선도, 지도/빅매치) 중심으로 구성

## 4) 변경 파일
- `apps/web/app/page.js`
- `apps/web/app/candidates/[candidate_id]/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue419_loading_copy_consistency_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue419_home_loading_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue419_home_loading_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue419_candidate_loading_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue419_candidate_loading_mobile.png`

## 5) 증빙 캡처
- 홈(Desktop): `UIUX_reports/screenshots/2026-02-26_issue419_home_loading_desktop.png`
- 홈(Mobile): `UIUX_reports/screenshots/2026-02-26_issue419_home_loading_mobile.png`
- 후보(Desktop): `UIUX_reports/screenshots/2026-02-26_issue419_candidate_loading_desktop.png`
- 후보(Mobile): `UIUX_reports/screenshots/2026-02-26_issue419_candidate_loading_mobile.png`

## 6) 검증
- `cd apps/web && npm run build` PASS

## 7) 상태 제안
- next_status: `status/in-review`

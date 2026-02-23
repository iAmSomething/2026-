# [UIUX][S2] 운영 품질패널 v2 + 스코프 배지 고정 보고서 (#221)

- 작성일: 2026-02-23
- 이슈: #221
- Report-Path: `UIUX_reports/2026-02-23_uiux_issue221_quality_panel_v2_scope_badge_report.md`

## 1) 작업 개요
운영 화면에서 데이터 품질을 즉시 해석할 수 있도록 품질패널을 v2로 개편했다.  
동시에 지역 상세(매치업) 상단에서 전국/지역 스코프를 항상 배지로 노출해 비교 기준 혼선을 줄였다.

## 2) 반영 내용
1. 홈 품질패널 v2 (`apps/web/app/page.js`)
- 3개 핵심 카드로 고정
  - `신선도 p90`
  - `완전성 (completeness)`
  - `공식확정 대기`
- 카드별 상태 등급(`ok/info/warn`)과 전체 상태 배지 추가
- `completeness_ratio` 미제공 시 폴백 경로를 추가해 운영값 미노출을 방지

2. 지역 상세 스코프 배지 고정 (`apps/web/app/matchups/[matchup_id]/page.js`)
- 상단 배지에 `조사 스코프`, `비교 기준`을 항상 노출
- `audience_scope`가 없을 때 `office_type`, `region_code`로 폴백 결정
- 비전국 스코프는 경고 카피로 직접 비교 금지 안내 고정

3. 스타일 보강 (`apps/web/app/globals.css`)
- 품질 카드 3열 레이아웃으로 정리
- 상태별 카드 톤(`.quality-item.ok/info/warn`) 추가
- 설명 카피와 기준 시각 푸터 스타일 정리

## 3) QA 재현 스크린샷 세트
1. 홈(Desktop): `UIUX_reports/screenshots/2026-02-23_issue221_quality_panel_v2_home_desktop.png`
2. 홈(Mobile): `UIUX_reports/screenshots/2026-02-23_issue221_quality_panel_v2_home_mobile.png`
3. 매치업(Desktop): `UIUX_reports/screenshots/2026-02-23_issue221_scope_badge_matchup_desktop.png`
4. 매치업(Mobile): `UIUX_reports/screenshots/2026-02-23_issue221_scope_badge_matchup_mobile.png`

## 4) 검증
1. 빌드 검증
- `apps/web`: `npm run build` PASS

2. 운영 API 샘플 저장
- `data/verification/issue221_dashboard_quality_sample.json`
- `data/verification/issue221_matchup_sample.json`

## 5) API 필드 매핑 체크리스트 첨부
- `UIUX_reports/2026-02-23_uiux_issue221_api_field_mapping_checklist.md`
- 결과: 필드명 매핑 불일치 0건

## 6) 변경 파일
1. `apps/web/app/page.js`
2. `apps/web/app/matchups/[matchup_id]/page.js`
3. `apps/web/app/globals.css`
4. `UIUX_reports/2026-02-23_uiux_issue221_quality_panel_v2_scope_badge_report.md`
5. `UIUX_reports/2026-02-23_uiux_issue221_api_field_mapping_checklist.md`
6. `UIUX_reports/screenshots/2026-02-23_issue221_quality_panel_v2_home_desktop.png`
7. `UIUX_reports/screenshots/2026-02-23_issue221_quality_panel_v2_home_mobile.png`
8. `UIUX_reports/screenshots/2026-02-23_issue221_scope_badge_matchup_desktop.png`
9. `UIUX_reports/screenshots/2026-02-23_issue221_scope_badge_matchup_mobile.png`
10. `data/verification/issue221_dashboard_quality_sample.json`
11. `data/verification/issue221_matchup_sample.json`

## 7) DoD 체크
- [x] 품질 상태 카드 디자인/카피 확정
- [x] 지역 상세 스코프 배지 고정
- [x] QA 재현 가능한 데스크톱/모바일 스크린샷 제출
- [x] API 필드명 매핑 불일치 0건 체크리스트 첨부

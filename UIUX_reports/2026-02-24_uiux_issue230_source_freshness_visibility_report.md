# [UIUX][S3] 실데이터 출처/신선도 가시화 패널 고도화 보고서 (#230)

- 작성일: 2026-02-24
- 이슈: #230
- Report-Path: `UIUX_reports/2026-02-24_uiux_issue230_source_freshness_visibility_report.md`

## 1) 작업 개요
대시보드에서 실데이터 여부/출처/신선도를 즉시 파악할 수 있도록 홈 품질패널과 카드/매치업 배지 체계를 강화했다.

## 2) 반영 사항
1. 홈 품질패널 고도화 (`apps/web/app/page.js`)
- `실데이터 소스(기사/NESDC)` 비중 표시 섹션 추가
- 품질 카드 3축 유지: `신선도 p90`, `완전성(completeness)`, `공식확정 대기`
- `실데이터 LIVE` 배지 고정 노출

2. 카드/매치업 배지 강화
- 홈 요약 카드/빅매치 카드에 아래 배지 반영
  - `source_channel`/`source_channels` -> 출처 배지
  - `is_official_confirmed` -> 공식확정/대기 배지
  - `freshness_hours` -> 신선도 배지
  - `needs_manual_review` 또는 지연 조건 -> 검수대기 배지
- 매치업 상세 상단/옵션행에도 동일 배지 체계 반영 (`apps/web/app/matchups/[matchup_id]/page.js`)

3. 데이터 없음/검수대기 상태 디자인 정리
- 품질 API 미응답 시 `데이터 없음` 패널 고정
- 카드/매치업에 `검수대기` 배지 스타일 통일
- 데모 파라미터(`state_demo=empty|review`)로 QA 재현 가능하도록 상태 분기 추가

4. 스타일 (`apps/web/app/globals.css`)
- source ratio meter 스타일 추가
- 카드/옵션 행 배지 레이아웃 정리
- 상태별 톤(`ok/info/warn`) 일관성 유지

## 3) 검증
1. 빌드
- `apps/web`: `npm run build` PASS

2. API 샘플 확보
- `data/verification/issue230_dashboard_summary_sample.json`
- `data/verification/issue230_big_matches_sample.json`
- `data/verification/issue230_map_latest_sample.json`
- `data/verification/issue230_matchup_sample.json`

## 4) 스크린샷 증빙
1. 홈(Desktop): `UIUX_reports/screenshots/2026-02-24_issue230_home_source_freshness_desktop.png`
2. 홈(Mobile): `UIUX_reports/screenshots/2026-02-24_issue230_home_source_freshness_mobile.png`
3. 매치업(Desktop): `UIUX_reports/screenshots/2026-02-24_issue230_matchup_source_badges_desktop.png`
4. 매치업(Mobile): `UIUX_reports/screenshots/2026-02-24_issue230_matchup_source_badges_mobile.png`
5. 데이터없음 상태(Mobile): `UIUX_reports/screenshots/2026-02-24_issue230_state_empty_mobile.png`
6. 검수대기 상태(Mobile): `UIUX_reports/screenshots/2026-02-24_issue230_state_review_mobile.png`
7. 매치업 데이터없음(Mobile): `UIUX_reports/screenshots/2026-02-24_issue230_matchup_empty_mobile.png`

## 5) 체크리스트
- `UIUX_reports/2026-02-24_uiux_issue230_api_field_mapping_checklist.md`
- 결과: API 필드명 매핑 불일치 0건

## 6) 변경 파일
1. `apps/web/app/page.js`
2. `apps/web/app/matchups/[matchup_id]/page.js`
3. `apps/web/app/globals.css`
4. `UIUX_reports/2026-02-24_uiux_issue230_source_freshness_visibility_report.md`
5. `UIUX_reports/2026-02-24_uiux_issue230_api_field_mapping_checklist.md`
6. `UIUX_reports/screenshots/2026-02-24_issue230_home_source_freshness_desktop.png`
7. `UIUX_reports/screenshots/2026-02-24_issue230_home_source_freshness_mobile.png`
8. `UIUX_reports/screenshots/2026-02-24_issue230_matchup_source_badges_desktop.png`
9. `UIUX_reports/screenshots/2026-02-24_issue230_matchup_source_badges_mobile.png`
10. `UIUX_reports/screenshots/2026-02-24_issue230_state_empty_mobile.png`
11. `UIUX_reports/screenshots/2026-02-24_issue230_state_review_mobile.png`
12. `UIUX_reports/screenshots/2026-02-24_issue230_matchup_empty_mobile.png`
13. `data/verification/issue230_dashboard_summary_sample.json`
14. `data/verification/issue230_big_matches_sample.json`
15. `data/verification/issue230_map_latest_sample.json`
16. `data/verification/issue230_matchup_sample.json`

## 7) DoD 체크
- [x] 메인 품질패널에 실데이터 소스 비중 표시
- [x] 카드/매치업 `source_channel`/`official_confirmed` 배지 반영
- [x] 데이터 없음/검수대기 상태 디자인 정리
- [x] 데스크톱/모바일 스크린샷 제출
- [x] API 필드명 매핑 체크리스트 갱신

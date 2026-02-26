# 2026-02-26 UIUX Issue #393 Search→Detail Transition UX Report

## 1) 이슈
- issue: #393 `[W6][UIUX][P1] 지역 검색→상세 전환 UX 개선`
- 목표: 검색 결과에서 지역 상세/매치업 이동 경로를 명확히 하고, 상태 오인을 줄이는 카드 구조로 개선

## 2) 구현 요약
1. 검색 결과 카드 정보 강화
- 카드에 `선거유형 요약`, `데이터 상태`, `최신 데이터 날짜`를 함께 노출
- 지역명은 `시/도 + 시/군/구` 풀네임으로 표기

2. CTA 일관화
- 검색 결과 카드 하단 CTA를 `지역 상세 보기`로 통일
- 선거 리스트 카드 하단 CTA를 `매치업 상세 보기` / `매치업 준비중`으로 고정

3. no-data 상태 문구 강화
- 검색 결과 없음: 재검색 가이드 문구 강화
- 선거 타입 필터 결과 없음: `전체 선거 보기` 대체 액션 CTA 제공

## 3) 상세 규칙
### 3.1 검색 결과 카드 요약 규칙
- region별 `GET /api/v1/regions/{region_code}/elections` 응답을 병렬 조회해 요약 생성
- 요약 필드
  - `officeTypes`: 선거유형 목록(최대 3개 + overflow)
  - `hasPollDataCount/totalCount`: 데이터 상태 판단
  - `latestSurveyEndDate`: 최신 데이터 일자

### 3.2 CTA 규칙
- 검색 결과 리스트: `지역 상세 보기`
- 선거 타입 리스트
  - 이동 가능(`latest_matchup_id` 또는 non-placeholder `matchup_id`): `매치업 상세 보기`
  - 이동 불가: `매치업 준비중`

### 3.3 no-data 카피 규칙
- 검색 결과 0건: `검색 결과가 없습니다. 시/도 포함 지역명을 입력해 다시 시도해 주세요.`
- 선거 필터 결과 0건: `조건에 맞는 선거가 없습니다. 다른 선거 타입을 선택하거나 지역을 변경해 주세요.`
- 대체 액션: `전체 선거 보기`

## 4) 변경 파일
- `apps/web/app/search/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue393_search_to_detail_transition_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue393_search_transition_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue393_search_transition_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue393_search_transition_nodata_mobile.png`

## 5) 증빙
- desktop(검색 결과): `UIUX_reports/screenshots/2026-02-26_issue393_search_transition_desktop.png`
- mobile(검색 결과): `UIUX_reports/screenshots/2026-02-26_issue393_search_transition_mobile.png`
- mobile(no-data): `UIUX_reports/screenshots/2026-02-26_issue393_search_transition_nodata_mobile.png`

## 6) 검증
- `cd apps/web && npm run build` PASS

## 7) 기대 효과(정성)
- 검색 결과 단계에서 선거유형/데이터상태를 먼저 확인 가능해 지역 상세 진입 전 맥락 손실 감소
- CTA 문구 통일로 검색→상세→매치업 이동 경로 인지 부담 감소

## 8) 상태 제안
- next_status: `status/in-review`

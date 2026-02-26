# 2026-02-26 UIUX Issue #373 Trendline Card Component Report

## 1) 이슈
- issue: #373 `[W4][UIUX][P2] 대시보드 추세선 카드 컴포넌트(정당/직무평가/선거성격)`
- 목표: 3지표 공통 추세선 카드 프레임 + source/scope 배지 표준화 + 모바일 축약 규칙 확정

## 2) 컴포넌트 설계
### 2.1 공통 프레임
- 카드 구성: 제목/설명 -> source/scope 배지 -> sparkline -> 최신값/변화 배지
- 상태 처리:
  - 시계열 2점 이상: sparkline 렌더링
  - 시계열 없음: `추세 데이터 연동 대기` empty-state
  - `trend_demo=1`: 샘플 프레임(데모 시계열) 생성

### 2.2 source/scope 배지 표준화
- source 배지: `summaryDataSourceTone/Label` 재사용 (`official|mixed|article`)
- scope 배지: `inferScope` 기반 `전국/광역/기초/미확인`

### 2.3 모바일 축약 규칙
- `@media (max-width: 980px)`에서 추세 카드 1열로 축약
- meta 라인(`trend-meta`) 폰트 축소
- sparkline 영역 고정 높이 유지(96px)

## 3) 필드 매핑 명세 (개발 연동)
| UI 필드 | API 우선 경로 | fallback |
|---|---|---|
| 정당 추세 points | `party_support_trend[]` | `trend_demo=1` 시 `party_support[].value_mid` 기반 샘플 생성 |
| 직무평가 추세 points | `president_job_approval_trend[]` | `trend_demo=1` 시 `president_job_approval[].value_mid` 기반 샘플 생성 |
| 선거성격 추세 points | `election_frame_trend[]` | `trend_demo=1` 시 `election_frame[].value_mid` 기반 샘플 생성 |
| source 배지 | `data_source` | `article` |
| scope 배지 | 각 지표 row의 `audience_scope` 다빈도 | `unknown` |
| 점 값 | point.`value_mid \| value \| y \| ratio` | 숫자 해석 실패 시 point 제외 |
| 점 라벨 | point.`survey_end_date \| date \| as_of` | `P{index}` |

## 4) QA 시각 기준
- 추세 카드 3종이 동일 레이아웃/간격/배지 규칙 유지
- sparkline path + point dot 렌더링 깨짐 없음
- 모바일에서 카드 1열 배치 및 텍스트 겹침 없음
- 연동 대기 상태에서 empty-state 문구 일관

## 5) 변경 파일
- `apps/web/app/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue373_trendline_card_component_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue373_trendline_cards_demo_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue373_trendline_cards_demo_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue373_trendline_cards_empty_mobile.png`

## 6) 증빙
- demo desktop: `UIUX_reports/screenshots/2026-02-26_issue373_trendline_cards_demo_desktop.png`
- demo mobile: `UIUX_reports/screenshots/2026-02-26_issue373_trendline_cards_demo_mobile.png`
- empty mobile: `UIUX_reports/screenshots/2026-02-26_issue373_trendline_cards_empty_mobile.png`
- capture URL:
  - demo: `/?trend_demo=1`
  - empty: `/`

## 7) 검증
- `cd apps/web && npm run build` PASS

## 8) 상태 제안
- next_status: `status/in-review`

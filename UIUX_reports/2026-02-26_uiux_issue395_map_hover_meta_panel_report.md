# 2026-02-26 UIUX Issue #395 Map Hover Meta Panel Enhancement Report

## 1) 이슈
- issue: #395 `[W7][UIUX][P2] 지도 Hover 메타 패널 고도화`
- 목표: hover/focus만으로 최신 조사 메타를 빠르게 파악하고, no-data 지역도 정보손실 없이 안내

## 2) 개선 내용
### 2.1 Hover 메타 필드 우선순위
- 지역명/코드 + 상태 배지(선택 고정/키보드 포커스/hover 미리보기)
- 최신 조사 여부 배지(있음/없음)
- 최신 조사 메타(우선순위)
  1. 최신 조사일
  2. 조사기관
  3. 표본
  4. 오차범위
  5. 채널

### 2.2 ADM2 -> ADM1 매핑 보강
- `map-latest`의 `region_code`가 ADM2(`11-110`)여도 ADM1(`11-000`) 패널에서 최신 데이터 매칭되도록 prefix 매핑 추가
- 결과: hover 패널에서 최신성 판단 가능한 지역 수 증가

### 2.3 No-data placeholder 강화
- 최신 조사 없음 상태에서도 메타 패널 고정 노출
- `최신 조사일/조사기관/표본/오차`를 placeholder로 명시하고 안내 문구 제공

### 2.4 접근성 포커스 상태 강화
- 지도 path 그룹에 `aria-label` 추가
- 키보드 포커스 시 `stroke` 강조 스타일 적용
- `focusedCode` 상태를 패널 활성 코드에 포함해 hover-only 의존성 완화

## 3) 변경 파일
- `apps/web/app/_components/RegionalMapPanel.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue395_map_hover_meta_panel_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_data_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_nodata_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_data_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_nodata_mobile.png`

## 4) 증빙
- data(Desktop): `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_data_desktop.png`
- no-data(Desktop): `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_nodata_desktop.png`
- data(Mobile): `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_data_mobile.png`
- no-data(Mobile): `UIUX_reports/screenshots/2026-02-26_issue395_map_hover_meta_nodata_mobile.png`
- capture URL:
  - data: `/?selected_region=42-000`
  - no-data: `/?selected_region=30-000`

## 5) 검증
- `cd apps/web && npm run build` PASS

## 6) 수용기준 대응
1. hover만으로 최신성 판단 가능
- 최신 조사 있음/없음 배지 + 최신 조사일 메타를 패널 상단에 고정
2. no-data 지역 정보손실 없이 안내
- placeholder 메타 필드 및 안내 문구 추가
3. QA a11y PASS
- 키보드 포커스 강조 + aria-label + focus 기반 패널 활성화 반영

## 7) 상태 제안
- next_status: `status/in-review`

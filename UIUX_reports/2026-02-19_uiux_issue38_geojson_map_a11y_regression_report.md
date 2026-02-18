# [UIUX] Issue #38 메인 지도 GeoJSON 실레이어 + 접근성 재회귀 보고서

- 보고일: 2026-02-19
- 이슈: #38 `[UIUX] 메인 지도 GeoJSON 실레이어 적용 + 접근성 재회귀`
- Report-Path: `UIUX_reports/2026-02-19_uiux_issue38_geojson_map_a11y_regression_report.md`

## 1) 작업 개요
- 목표: 홈 지도 영역을 mock 버튼 그리드에서 GeoJSON SVG 레이어로 전환하고 모바일/접근성 회귀를 완료.
- 범위: 지도 렌더 컴포넌트 교체, fixture/geo 데이터 보강, 회귀 체크리스트 및 시연 스크린샷 제출.

## 2) 구현 내역
1. GeoJSON 실레이어 적용
- `/public/geo/kr_adm1_simplified.geojson` 추가
- `MapInteractionPrototype`에서 GeoJSON fetch + SVG path 투영 렌더 적용

2. 모바일 인터랙션 회귀
- 모바일(coarse pointer) 환경에서 hover 비의존 로직 유지
- `tap_region -> panel_open`, `tap_same_region -> idle` 상태 유지

3. 접근성 재검증
- `role=button`, `tabIndex`, `aria-label`, `aria-pressed`, `aria-live` 반영
- Enter/Space 키보드 동작 + hit-area 확장(투명 stroke) 반영

4. 데이터 매핑
- `map-latest` fixture에 GeoJSON region_code 집합 보강
- 선택 지역이 `map-latest` 미매핑일 때 안내 메시지 분기 제공

## 3) 변경 파일
- `apps/web/components/home/MapInteractionPrototype.tsx`
- `apps/web/public/geo/kr_adm1_simplified.geojson`
- `apps/web/public/mock_fixtures_v0.2/dashboard_map_latest.json`
- `poll_uiux_docs_v0.1/MAP_GEOJSON_A11Y_REGRESSION_v0.3.md`

## 4) 시연 스크린샷
1. 데스크톱 기본 지도: `UIUX_reports/screenshots/2026-02-19_home_geojson_desktop.png`
2. 데스크톱 선택 상태: `UIUX_reports/screenshots/2026-02-19_home_geojson_desktop_selected.png`
3. 모바일 선택 상태: `UIUX_reports/screenshots/2026-02-19_home_geojson_mobile_selected.png`

## 5) 접근성 회귀 체크 결과
- 체크리스트 문서: `poll_uiux_docs_v0.1/MAP_GEOJSON_A11Y_REGRESSION_v0.3.md`
- 항목 수: 10
- 통과: 10
- 실패: 0
- 통과율: 100%

## 6) UI/API 필드 불일치 점검
- 기준: `/api/v1/dashboard/map-latest` + snake_case
- 점검 필드: `region_code`, `region_name`, `has_data`, `latest.matchup_id`, `latest.value_mid`
- 결과: 불일치 0건

## 7) 빌드 검증
- `cd apps/web && npm run build` PASS
- `cd apps/web && npm run typecheck` PASS

## 8) 완료기준 충족 여부
1. 데스크톱/모바일 시연 스크린샷 제출: 충족
2. 접근성 회귀 체크리스트 통과: 충족(100%)
3. UIUX 보고서 제출: 충족

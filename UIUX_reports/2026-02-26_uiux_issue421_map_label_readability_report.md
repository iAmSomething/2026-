# 2026-02-26 UIUX Issue #421 Map Label Readability Report

## 1) 이슈
- issue: #421 `[W10][UIUX][P2] 광역 지도 라벨 가독성·겹침 완화`
- 목표: 지도 라벨의 겹침/밀집 가독성을 개선하고 모바일 라벨 밀도를 낮춥니다.

## 2) 구현 요약
1. 지도 라벨 레이어 추가
- 광역 코드별 short label(`서울`, `경기`, `강원` 등) 렌더링
- path 위 텍스트 오버레이로 즉시 지역 식별 가능

2. 밀집 지역 오프셋 규칙 적용
- 수도권/동남권 중심으로 label 좌표 보정값 적용
- 기본 중심점만 사용할 때 발생하는 겹침을 완화

3. 모바일 라벨 밀도 규칙
- 밀집 라벨(optional)은 모바일에서 기본 숨김
- 단, 선택(active) 라벨은 항상 유지하여 상호작용 인지성 보장

## 3) 컴포넌트/스타일 스펙
- `REGION_SHORT_LABELS`: 시도 약칭 표기 사전
- `LABEL_OFFSETS`: 밀집 지역 라벨 오프셋 보정
- `DENSE_LABEL_CODES`: 모바일 축약 대상 라벨 코드
- `.map-label`: 고대비 텍스트(white stroke)로 배경 지형 위 가독성 확보
- `.map-label.optional:not(.active)`: 모바일에서 숨김 처리

## 4) 변경 파일
- `apps/web/app/_components/RegionalMapPanel.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue421_map_label_readability_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue421_map_label_desktop_default.png`
- `UIUX_reports/screenshots/2026-02-26_issue421_map_label_desktop_selected.png`
- `UIUX_reports/screenshots/2026-02-26_issue421_map_label_mobile_default_full.png`
- `UIUX_reports/screenshots/2026-02-26_issue421_map_label_mobile_selected_full.png`

## 5) 증빙 캡처
- desktop(default): `UIUX_reports/screenshots/2026-02-26_issue421_map_label_desktop_default.png`
- desktop(selected_region=31): `UIUX_reports/screenshots/2026-02-26_issue421_map_label_desktop_selected.png`
- mobile(default full): `UIUX_reports/screenshots/2026-02-26_issue421_map_label_mobile_default_full.png`
- mobile(selected_region=31 full): `UIUX_reports/screenshots/2026-02-26_issue421_map_label_mobile_selected_full.png`

## 6) 검증
- `cd apps/web && npm run build` PASS

## 7) 상태 제안
- next_status: `status/in-review`

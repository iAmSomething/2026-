# 2026-02-26 UIUX Issue #396 Operational Quality Panel v3 Report

## 1) 이슈
- issue: #396 `[W8][UIUX][P2] 운영 품질 패널 v3 카피/레이아웃 개선`
- 목표: 기술 사용자 중심 표현을 운영 액션 중심 표현으로 전환

## 2) v3 핵심 변경
### 2.1 경고 우선순위 정렬
- 품질 신호를 `warn -> info -> ok` 순으로 자동 정렬
- 상단 배너에서 `경고 항목 N건` 집계 노출
- 경고 존재 시 우선 확인 지시문(처리 순서 안내) 노출

### 2.2 액션 지시문 추가
- 각 신호 카드에 `확인 액션` 문장을 고정 추가
- 신호별 액션 예시
  - 신선도 지연: 최근 48시간 수집 누락 확인 + 수집 재실행
  - 공식확정 대기: 상위 영향 항목 공식 출처 보강
  - 검수 대기열: 24시간 초과 대기 항목 우선 처리
  - 완전성 지표: 누락 필드/스키마 매핑 재점검
  - 출처 편중: NESDC/공식 채널 보강

### 2.3 상태별 한국어 카피 통일
- 상태 라벨을 `정상/주의/경고`로 통일
- 제목/본문 카피를 한국어 중심 운영 문구로 정규화
- footnote 표현도 `기준 시각/상태 코드`로 정리

## 3) 정보구조 재편
- 기존: 3개 지표 카드 + 소스 비중
- v3: 우선순위 배너 + 5개 신호 카드(경고 우선 정렬) + 소스 비중

## 4) 변경 파일
- `apps/web/app/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue396_operational_quality_panel_v3_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue396_quality_panel_v3_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue396_quality_panel_v3_mobile.png`

## 5) 증빙
- desktop: `UIUX_reports/screenshots/2026-02-26_issue396_quality_panel_v3_desktop.png`
- mobile: `UIUX_reports/screenshots/2026-02-26_issue396_quality_panel_v3_mobile.png`
- capture URL: `/`

## 6) 검증
- `cd apps/web && npm run build` PASS

## 7) 수용기준 대응
1. 오류 원인 추적 시간 단축
- 경고 우선 정렬 + 카드별 확인 액션으로 탐색 경로 단축
2. 카피 일관성 규칙 준수
- 상태 라벨/설명 문구를 `정상/주의/경고` 체계로 통일
3. QA 리뷰 통과
- 데스크톱/모바일 캡처 및 빌드 검증 제출

## 8) 상태 제안
- next_status: `status/in-review`

# 2026-02-26 UIUX Issue #392 Badge IA Reorder Report

## 1) 이슈
- issue: #392 `[W5][UIUX][P1] 품질/출처/신선도 배지 IA 재정렬`
- 목표: 배지 의미 계층을 재정렬해 핵심 상태를 3초 내 파악 가능하게 개선

## 2) IA 재정의
### 2.1 우선순위 규칙 (핵심 → 보조)
1. 품질 신호 (`품질 검수대기/품질 확인됨/품질 확인중`)
2. 출처 신호 (`출처 NESDC/혼합/기사/미확인`)
3. 신선도 (`신선도 Nh`)
4. 보조: 공식확정 (`공식확정/공식확정 대기`)

### 2.2 색상/문구 규칙
| 배지 | tone | 기준 |
|---|---|---|
| 품질 검수대기 | warn | `needs_manual_review=true` 또는 신선도/확정 조건으로 검수 필요 |
| 품질 확인됨 | ok | `is_official_confirmed=true` && `freshness<=48h` |
| 품질 확인중 | info | 그 외 중간 상태 |
| 출처 배지 | ok/info/warn | `source_channel(s)` 기준 |
| 신선도 배지 | ok/info/warn | `<=48h / <=96h / >96h` |
| 공식확정 배지(보조) | ok/warn | `is_official_confirmed` |

## 3) 접근성/상세 설명
- 모든 상태 배지에 `title` + `aria-label` 기반 상세 설명 tooltip 추가
- 색상 외에도 텍스트로 상태를 직접 표기해 색상 의존성 축소
- 배지 내 `i` 힌트 마크를 추가해 설명 존재를 시각적으로 명시

## 4) 모바일 축약 규칙
- `badge-optional`(공식확정 배지)는 모바일(`max-width: 980px`)에서 자동 숨김
- 핵심 3배지(품질/출처/신선도)만 유지
- 모바일에서 배지 간격/폰트/패딩 축소로 밀도 최적화

## 5) 적용 범위
- 홈 대시보드 요약 카드(`SummaryColumn`) 배지 영역
- 홈 대시보드 빅매치 카드(`BigMatchCards`) 배지 영역

## 6) 변경 파일
- `apps/web/app/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue392_badge_ia_reorder_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue392_badge_ia_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue392_badge_ia_mobile.png`

## 7) 증빙
- desktop: `UIUX_reports/screenshots/2026-02-26_issue392_badge_ia_desktop.png`
- mobile: `UIUX_reports/screenshots/2026-02-26_issue392_badge_ia_mobile.png`
- 캡처 URL: `/?state_demo=review`

## 8) 검증
- `cd apps/web && npm run build` PASS

## 9) 상태 제안
- next_status: `status/in-review`

# [UIUX][S2] API 필드 매핑 체크리스트 (#221)

- 작성일: 2026-02-23
- 기준 API 샘플:
  - `data/verification/issue221_dashboard_quality_sample.json`
  - `data/verification/issue221_matchup_sample.json`

## 1) 품질 패널 v2 매핑

| UI 항목 | 1차 필드(계약) | 폴백 필드 | snake_case 일치 | 비고 |
|---|---|---|---|---|
| 신선도 p90 카드 | `freshness_p90_hours` | 없음 | PASS | 시간 단위 카드 |
| 완전성(completeness) 카드 | `completeness_ratio` | `completeness.ratio` -> `legal_completeness_score` -> `official_confirmed_ratio` | PASS | 완전성 미노출 환경 대비 폴백 |
| 공식확정 대기 카드 | `official_pending_count` | `official_confirmation.unconfirmed_count` -> `official_pending_ratio` -> `1 - official_confirmed_ratio` | PASS | 공식확정 대기 규모 |
| 기준 시각 푸터 | `generated_at` | 없음 | PASS | 패널 하단 기준 시각 |
| 운영 상태 라벨 | `quality_status` | 없음 | PASS | 전체 상태 보조 노출 |

## 2) 지역 상세 스코프 배지 매핑

| UI 항목 | 1차 필드(계약) | 폴백 필드 | snake_case 일치 | 비고 |
|---|---|---|---|---|
| 조사 스코프 배지 | `audience_scope` | `office_type`, `region_code` | PASS | `전국/지역(광역)/기초` 고정 라벨 |
| 비교 기준 배지 | `audience_scope` | `office_type`, `region_code` | PASS | `전국 vs 전국` 또는 `지역/기초 vs 지역/기초` |

## 3) 결과
- 필드명 매핑 불일치: **0건**
- camelCase 혼입: **0건**
- 필수 노출 항목 누락: **0건**

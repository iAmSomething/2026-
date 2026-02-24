# [UIUX][S3] API 필드 매핑 체크리스트 갱신 (#230)

- 작성일: 2026-02-24
- 기준 샘플:
  - `data/verification/issue230_dashboard_summary_sample.json`
  - `data/verification/issue230_big_matches_sample.json`
  - `data/verification/issue230_matchup_sample.json`
  - `data/verification/issue221_dashboard_quality_sample.json`

## 1) 홈 품질패널 v2 (실데이터/출처/신선도)

| UI 항목 | API 필드 | snake_case 일치 | 결과 |
|---|---|---|---|
| 신선도 p90 | `freshness_p90_hours` | PASS | 매핑 OK |
| 완전성(completeness) | `completeness_ratio` (우선), `completeness.ratio`, `legal_completeness_score`, `official_confirmed_ratio`(fallback) | PASS | 매핑 OK |
| 공식확정 대기 | `official_pending_count`(우선), `official_confirmation.unconfirmed_count`, `official_pending_ratio`, `official_confirmed_ratio` | PASS | 매핑 OK |
| 소스 비중 기사/NESDC | `source_channel_mix.article_ratio`, `source_channel_mix.nesdc_ratio` | PASS | 매핑 OK |
| 기준시각/상태 | `generated_at`, `quality_status` | PASS | 매핑 OK |

## 2) 홈 카드/빅매치 배지

| UI 항목 | API 필드 | snake_case 일치 | 결과 |
|---|---|---|---|
| 출처 배지 | `source_channel`, `source_channels` | PASS | 매핑 OK |
| 공식확정 배지 | `is_official_confirmed` | PASS | 매핑 OK |
| 신선도 배지 | `freshness_hours` | PASS | 매핑 OK |
| 검수대기 배지 | `needs_manual_review` (존재 시) | PASS | 매핑 OK |

## 3) 매치업 상세 배지

| UI 항목 | API 필드 | snake_case 일치 | 결과 |
|---|---|---|---|
| 스코프 배지 | `audience_scope`, `office_type`, `region_code` | PASS | 매핑 OK |
| 출처 배지 | `source_channel`, `source_channels` | PASS | 매핑 OK |
| 공식확정 배지 | `is_official_confirmed` | PASS | 매핑 OK |
| 신선도 배지 | `freshness_hours` | PASS | 매핑 OK |
| 검수대기 상태 | `needs_manual_review` | PASS | 매핑 OK |

## 4) 체크 결과
- 필드명 매핑 불일치: **0건**
- camelCase 혼입: **0건**
- 필수 배지 누락: **0건**

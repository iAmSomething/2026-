# 2026-02-26 UIUX Issue #371 Region 3-Slot Layout Report

## 1) 이슈
- issue: #371 `[W2][UIUX][P1] 지역 인터랙션 3슬롯(단체장/의회/교육감) 고정 레이아웃 가이드`
- 목표: 지역 인터랙션 패널에서 광역 3종 슬롯(단체장/의회/교육감)을 고정 순서로 노출하고, placeholder/오표기 방지 규칙을 확정

## 2) 구현 요약
1. 3슬롯 고정 순서 적용
- 순서 고정: `광역자치단체장 -> 광역의회 -> 교육감`
- API 응답 순서와 무관하게 슬롯 순서를 강제

2. 코드 정규화 및 오표기 방지
- 지도/선택 코드는 `KR-xx`, API 호출 코드는 `xx-000`으로 정규화
- `selected_region=29`/`KR-29`/`29-000` 모두 동일 지역으로 처리
- 선택 지역 prefix와 불일치하는 elections row는 UI 노출에서 제외

3. 슬롯 대표값 선택 규칙
- office_type 정규화(`metro_mayor|광역자치단체장` 등) 후 슬롯 매핑
- 중복 row가 있을 경우 대표 1건 선택:
  - `has_poll_data=true` 우선
  - `latest_survey_end_date` 최신 우선

4. placeholder/배지 규칙 고정
- `loading`: 불러오는 중
- `error`: 조회 실패
- `has_poll_data=true`: 조사 데이터 있음
- 그 외: 조사 데이터 없음
- placeholder row(`is_placeholder=true`)는 `placeholder` 배지로 명시

## 3) 컴포넌트 스펙 (Handoff)
| 컴포넌트 | 역할 | 입력 필드 | 출력/동작 |
|---|---|---|---|
| `RegionalMapPanel` | 지도 선택 + 우측 슬롯 패널 | `items`, `apiBase`, `initialSelectedRegionCode` | 선택 지역 코드 정규화, API 호출, 슬롯 렌더 |
| `region-slot-list` | 3슬롯 컨테이너 | `elections[]`, `selectedCode` | 고정 순서 슬롯 카드 3개 |
| `slot-card` | 슬롯 1개 | `office_type`, `title`, `has_poll_data`, `latest_survey_end_date`, `is_placeholder`, `latest_matchup_id` | 상태 배지 + 제목 + 최신일 + 상세 링크/없음 |

## 4) 상태 카피 사전
| 상태 | 카피 | tone |
|---|---|---|
| 로딩 | 불러오는 중 | info |
| 조회 실패 | 조회 실패 | warn |
| 데이터 있음 | 조사 데이터 있음 | ok |
| 데이터 없음/placeholder | 조사 데이터 없음 | warn |
| 지역 불일치 제외 | 선택 지역과 다른 코드 N건은 표시에서 제외했습니다. | warn |

## 5) API/필드 매핑
- API: `GET /api/v1/regions/{region_code}/elections`
- 사용 필드:
  - `matchup_id`, `latest_matchup_id`
  - `region_code`, `office_type`, `title`
  - `has_poll_data`, `has_candidate_data`
  - `latest_survey_end_date`
  - `is_placeholder`, `is_fallback`

## 6) 증빙
1. UI 캡처 (세종)
- desktop: `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_sejong_desktop.png`
- mobile: `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_sejong_mobile.png`

2. UI 캡처 (강원)
- desktop: `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_gangwon_desktop.png`
- mobile: `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_gangwon_mobile.png`

3. API 샘플
- `UIUX_reports/2026-02-26_issue371_region_slots_api_samples.json`

## 7) 변경 파일
- `apps/web/app/_components/RegionalMapPanel.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue371_region_3slot_layout_report.md`
- `UIUX_reports/2026-02-26_issue371_region_slots_api_samples.json`
- `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_sejong_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_sejong_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_gangwon_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue371_region_slots_gangwon_mobile.png`

## 8) 검증
- `cd apps/web && npm run build` PASS

## 9) 상태 제안
- next_status: `status/in-review`

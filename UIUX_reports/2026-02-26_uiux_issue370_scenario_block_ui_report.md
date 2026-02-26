# 2026-02-26 UIUX Issue #370 Scenario Block UI Report

## 1) 이슈
- issue: #370 `[W1][UIUX][P1] 매치업 상세 시나리오 블록 UI(양자/다자 분리) 정식 디자인`
- 목표: 혼합 기사 시나리오를 양자/다자 단위 카드로 분리해 값 혼입 오인을 제거

## 2) 구현 요약
1. 시나리오 그룹 분리
- `head_to_head` -> `양자 시나리오`
- `multi_candidate` -> `다자 시나리오`
- 그룹별 카드 그리드로 분리 렌더

2. 시나리오 카드 구조 고정
- 카드 헤더: 시나리오 유형 배지 + 시나리오 제목 배지
- 후보 블록: 후보명/수치/막대/출처·공식확정·검수대기 배지/정당/원문/프로필 링크

3. 모바일 레이아웃 대응
- 980px 이하에서 시나리오 카드 그리드 1열 강제
- 후보 블록 카드형 경계 유지로 스크롤 시 그룹 혼동 최소화

4. QA 데모 파라미터 추가
- `scenario_demo=triad` 지원
- 실데이터 옵션 부족 시에도 양자 2 + 다자 1 구조를 강제 생성해 시각 검증 가능

## 3) 변경 파일
- `apps/web/app/matchups/[matchup_id]/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-26_uiux_issue370_scenario_block_ui_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue370_scenario_blocks_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue370_scenario_blocks_mobile.png`

## 4) 상태별 렌더 규칙
| 상태 | 조건 | 렌더 규칙 |
|---|---|---|
| 기본 | `matchup.scenarios` 존재 | `scenario_type` 기준으로 양자/다자 그룹 분리 후 카드 렌더 |
| fallback | `matchup.scenarios` 없음 | `matchup.options` 기반 기본 시나리오 1개 생성 |
| 빈 상태 | `state_demo=empty` 또는 옵션 0 | 후보 블록에 `데이터 없음` 안내 표시 |
| 검수 대기 | `state_demo=review` 또는 `needs_manual_review=true` | 후보 행에 `검수대기` 배지 표시 |
| 혼합 출처 | `source_channels`에 `article+nesdc` | 출처 배지를 `출처 혼합`으로 노출 |
| QA triad 데모 | `scenario_demo=triad` | 양자 2개 + 다자 1개 시나리오 카드 강제 구성 |

## 5) API/필드 사용 명세 (시나리오 UI)
| UI 영역 | 필드 |
|---|---|
| 그룹 분류 | `scenarios[].scenario_type`, `scenarios[].options[].value_mid` |
| 시나리오 헤더 | `scenarios[].scenario_title`, `scenarios[].scenario_key` |
| 후보 행 | `scenarios[].options[].option_name`, `party_name`, `value_mid`, `value_raw`, `candidate_id`, `needs_manual_review` |
| 공통 배지 | `source_channel`, `source_channels`, `is_official_confirmed`, `freshness_hours` |

## 6) 증빙
- desktop: `UIUX_reports/screenshots/2026-02-26_issue370_scenario_blocks_desktop.png`
- mobile: `UIUX_reports/screenshots/2026-02-26_issue370_scenario_blocks_mobile.png`
- 캡처 URL: `/matchups/m_2026_seoul_mayor?scenario_demo=triad`

## 7) 검증
- `cd apps/web && npm run build` PASS

## 8) 의존성/리스크
- 선행 이슈 `#363`은 collector 분리 규칙셋(v2)이며, 본 UI는 현재 필드 기준 렌더 구조를 선반영
- 실데이터 시나리오가 확정되면 `scenario_type` enum 확장 여부만 추가 반영하면 됨

## 9) 상태 제안
- next_status: `status/in-review`

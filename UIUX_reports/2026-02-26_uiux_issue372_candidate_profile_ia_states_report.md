# 2026-02-26 UIUX Issue #372 Candidate Profile IA & Missing State Report

## 1) 이슈
- issue: #372 `[W3][UIUX][P2] 후보 프로필 페이지 IA 및 결측 상태 UX 확정`
- 목표: 후보 프로필 정보 구조를 고정하고 결측 상태(ready/partial/empty) UX를 일관화

## 2) IA 고정안 (후보 상세)
### 2.1 섹션 순서
1. 이동 경로
2. 후보 Hero
3. 상태/시나리오 배지
4. 소속/확정 상태
5. 출처/신선도 패널
6. 약력/출마 정보(MVP 최소필드)
7. 관련 매치업 요약

### 2.2 IA 다이어그램(텍스트)
- 후보 상세
  - 이동 경로(진입 출처, 복귀 링크)
  - 후보 식별(Hero)
  - 상태 배지/카피(ready/partial/empty + demo 파라미터)
  - 프로필 본문
    - 소속/확정 상태
    - 출처/신선도
    - 약력/출마
    - 관련 매치업

## 3) 3상태 UX 규칙
| 상태 | 배지 | 노출 규칙 | 카피 |
|---|---|---|---|
| `ready` | `프로필 준비됨` | 핵심 필드 전부 노출 | 핵심 프로필 필드가 준비된 상태 |
| `partial` | `부분 프로필` | 누락 필드는 `-` 또는 보강 안내 | 일부 필드만 확인, 검수 후 보강 |
| `empty` | `프로필 없음` | 약력/출마 카드에 empty-state 우선 | 후보 기본 프로필 비어 있음, 출처 확보 후 자동 갱신 |

## 4) 라우팅 UX 일관화
- `from=matchup&matchup_id=...` 진입 시 상단 `이동 경로` 패널에서 `이전 화면으로` 제공
- 항상 `대시보드`, `지역 검색` 링크 동시 제공
- 관련 매치업 조회는 `matchup_id` 우선 조회 후 alias fallback 조회

## 5) 구현 상세
- `state_demo` 쿼리 파라미터 추가 (`ready|partial|empty`)
- 후보 payload를 상태별로 가공하는 `applyStateDemo` 적용
- 데이터 충족도 기반 상태 계산 `profileState` 추가
- 상태별 배지/카피 매핑 `stateMeta` 추가
- 기존 단일 정보 블록을 IA 기준 4개 카드(소속/출처/약력/관련매치업)로 분리

## 6) 변경 파일
- `apps/web/app/candidates/[candidate_id]/page.js`
- `UIUX_reports/2026-02-26_uiux_issue372_candidate_profile_ia_states_report.md`
- `UIUX_reports/screenshots/2026-02-26_issue372_candidate_ready_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue372_candidate_partial_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue372_candidate_empty_desktop.png`
- `UIUX_reports/screenshots/2026-02-26_issue372_candidate_ready_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue372_candidate_partial_mobile.png`
- `UIUX_reports/screenshots/2026-02-26_issue372_candidate_empty_mobile.png`

## 7) 증빙
- URL(ready): `/candidates/cand-jwo?from=matchup&matchup_id=m_2026_seoul_mayor&state_demo=ready`
- URL(partial): `/candidates/cand-jwo?from=matchup&matchup_id=m_2026_seoul_mayor&state_demo=partial`
- URL(empty): `/candidates/cand-jwo?from=matchup&matchup_id=m_2026_seoul_mayor&state_demo=empty`
- desktop/mobile 3상태 캡처 총 6장 첨부

## 8) 검증
- `cd apps/web && npm run build` PASS

## 9) 상태 제안
- next_status: `status/in-review`

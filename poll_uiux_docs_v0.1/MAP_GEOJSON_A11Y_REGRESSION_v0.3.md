# MAP GeoJSON 접근성/모바일 회귀 테스트 (v0.3)

- 문서 버전: v0.3
- 최종 수정일: 2026-02-19
- 작성자: UIUX
- 대상 컴포넌트: `apps/web/components/home/MapInteractionPrototype.tsx`

## 1. 목적
- 버튼 그리드 기반 mock 지도를 GeoJSON SVG 실레이어로 교체한 이후, 모바일/접근성 회귀가 없는지 확인한다.

## 2. 상태 전이
| 현재 상태 | 이벤트 | 다음 상태 | 기대 결과 |
|---|---|---|---|
| `idle` | `hover_region(code)` (desktop) | `panel_preview` | 패널이 선택 전 미리보기로 갱신 |
| `idle` | `tap_region(code)` (mobile) | `panel_open` | 지역 선택 강조 + 패널 상세 표시 |
| `panel_open` | `tap_same_region(code)` | `idle` | 선택 해제 + 기본 안내 문구 표시 |
| `panel_open` | `tap_other_region(code)` | `panel_open` | 선택 지역 전환 + 패널 데이터 교체 |
| `panel_open` | `press_enter_region(code)` | `panel_open` | 키보드로 동일 전환 동작 |
| `panel_open` | `tap_matchup_cta` | `navigating` | `/matchups/{matchup_id}` 이동 |

## 3. 접근성 체크리스트
1. GeoJSON region 인터랙션 노드는 `role=button` + `tabIndex=0` 제공
2. `aria-label`에 지역명/데이터 유무 정보 제공
3. `aria-pressed`로 선택 상태 전달
4. 키보드 Enter/Space로 선택/해제 가능
5. 패널 영역 `aria-live=polite`로 업데이트 알림
6. 모바일에서 hover 의존 없이 tap만으로 동작
7. 선택 해제 버튼 제공(탭 상태 복구 가능)
8. 데이터 미연동/빈데이터 메시지 분기 제공
9. focus 이동 시 시각적 강조(stroke/active 상태) 식별 가능
10. hit-area 확장을 위한 투명 stroke 레이어 제공

## 4. 판정 기준
1. 상태 전이 시나리오 6개 모두 PASS
2. 접근성 체크리스트 10개 모두 PASS
3. 데스크톱/모바일 시연 스크린샷 제출

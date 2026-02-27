# 2026-02-27 UIUX Issue #467 Matchup Scenario Layout Report

## 1) 이슈
- issue: #467 `[UIUX][P1] 매치업 상세 정보구조 재배치(선거명 타이틀 + 시나리오 섹션)`
- 목표: 매치업 화면을 기사 제목 중심이 아닌 선거 단위 중심으로 재구성하고, 양자/다자 시나리오를 분리 노출합니다.

## 2) 구현 요약
1. 헤더 구조 재배치
- H1을 `선거 단위 제목`으로 전환(예: 서울시장)
- 서브타이틀에 기사 제목 + 조사기관/기간을 결합
- canonical 제목은 보조 정보로 하향

2. 시나리오 섹션 분리
- 양자/다자 그룹을 탭 행(`시나리오 섹션`)으로 분리 진입
- 그룹별 카드 유지 + 후보별 `프로필` CTA 유지

3. 메타데이터 우선순위 조정
- 상단 우선 배지: 조사기관/표본/응답률/오차범위
- `region_code`, `office_type`, `matchup_id`는 하단 보조 정보로 이동

## 3) 수용기준 대응
- 타이틀 맥락 혼동 완화: 선거 단위 제목을 H1으로 고정
- 다중 시나리오 분리: 양자/다자 탭 행 + 그룹 섹션 분리
- 모바일/데스크톱 캡처: 제출 완료

## 4) 변경 파일
- `apps/web/app/matchups/[matchup_id]/page.js`
- `apps/web/app/globals.css`
- `UIUX_reports/2026-02-27_uiux_issue467_matchup_scenario_layout_report.md`
- `UIUX_reports/screenshots/2026-02-27_issue467_matchup_ia_desktop.png`
- `UIUX_reports/screenshots/2026-02-27_issue467_matchup_ia_mobile.png`

## 5) 증빙
- desktop(full): `UIUX_reports/screenshots/2026-02-27_issue467_matchup_ia_desktop.png`
- mobile(full): `UIUX_reports/screenshots/2026-02-27_issue467_matchup_ia_mobile.png`
- URL: `/matchups/m_2026_seoul_mayor?scenario_demo=triad`

## 6) 검증
- `cd apps/web && npm run build` PASS

## 7) 상태 제안
- next_status: `status/in-review`

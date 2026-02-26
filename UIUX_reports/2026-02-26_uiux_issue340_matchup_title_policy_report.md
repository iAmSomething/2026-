# 2026-02-26 UIUX Issue #340 Matchup Title Policy Report

## 1) 이슈
- issue: #340 `[UIUX][P1] 매치업 상세 제목 정책 개편(선거명 우선, 기사제목 부제)`
- 목표: 매치업 상세 상단 제목을 canonical 선거명(지역+선거유형)으로 고정하고, 기사형 제목은 부제로 분리

## 2) 구현 내용
1. 상단 제목 canonical 고정
- 기존: `data.matchup.title` 직접 노출
- 변경: `region_code + office_type` 기반 canonical 타이틀 생성
  - 예: `KR-11-000 + metro_mayor` -> `서울특별시 광역자치단체장`

2. 기사 제목을 부제로 분리
- 카드 본문 상단에 `기사 제목: ...` 라인을 추가
- 같은 블록에서 `출처(조사기관) / 조사기간`을 함께 표기

3. 네비게이션 메타 일관화
- 유입 배지의 raw 코드(`region_code`, `office_type`)를 사용자 친화 라벨로 변경
  - `유입 지역: 서울특별시`
  - `유입 선거유형: 광역자치단체장`

4. fixture 시나리오 보강
- 매치업 fixture title을 기사형 문자열(`설 민심 여론조사`)로 변경
- canonical 제목과 기사 부제가 분리되어 보이는 상태를 기본 검증 가능하게 구성

## 3) 변경 파일
- `/Users/gimtaehun/election2026_codex/apps/web/app/matchups/[matchup_id]/page.tsx`
- `/Users/gimtaehun/election2026_codex/apps/web/public/mock_fixtures_v0.2/matchups_m_2026_seoul_mayor.json`

## 4) 증빙
1. before/after 1:1 비교 (desktop)
- before(runtime): `/Users/gimtaehun/election2026_codex/UIUX_reports/screenshots/2026-02-26_issue340_runtime_before_desktop.png`
- after(local patched): `/Users/gimtaehun/election2026_codex/UIUX_reports/screenshots/2026-02-26_issue340_matchup_title_policy_desktop.png`

2. before/after 1:1 비교 (mobile)
- before(runtime): `/Users/gimtaehun/election2026_codex/UIUX_reports/screenshots/2026-02-26_issue340_runtime_before_mobile.png`
- after(local patched): `/Users/gimtaehun/election2026_codex/UIUX_reports/screenshots/2026-02-26_issue340_matchup_title_policy_mobile.png`

3. `/api/v1/matchups/{id}` 샘플 정합 (현 상태)
- 운영/로컬 모두 `/api/v1/matchups/{id}` 직접 호출은 404(백엔드 라우트 미노출) 확인
- 현재 UI는 fallback fixture 경로로 정상 렌더링:
  - `/Users/gimtaehun/election2026_codex/apps/web/public/mock_fixtures_v0.2/matchups_m_2026_seoul_mayor.json`
- 따라서 제목 정책 검증은 화면 캡처 + fixture payload 정합으로 수행

## 5) 검증
- typecheck: `cd /Users/gimtaehun/election2026_codex/apps/web && npm run typecheck` PASS

## 6) 수용기준 매핑
- 제목만으로 선거구/선거유형 오인 0: canonical 제목 강제 생성으로 충족
- 기사 제목은 부제 유지: `기사 제목` 라인으로 충족
- 네비게이션/링크 회귀 없음: 기존 `matchup_id` 기반 라우팅/링크 유지

## 7) 상태 제안
- next_status: `status/in-review`

## 8) 배포/PR 상태 (2026-02-26)
- clean PR: `https://github.com/iAmSomething/2026-/pull/355`
- superseded PR(closed): `https://github.com/iAmSomething/2026-/pull/354`
- CI:
  - `validate-report-path` PASS
  - `phase1-qa` PASS
  - `Vercel` FAILURE (`https://vercel.com/st939823s-projects/2026-deploy/6z7aJwzPdmyhHeKxhUnq8XshiNW3`)

## 9) 현재 블로커
- 운영 after 캡처는 배포 실패로 아직 확보 불가
- `/api/v1/matchups/{id}` 운영 직접 호출은 404로 샘플 2건 캡처 조건 충족 불가(현재 UI는 fallback fixture 기반)

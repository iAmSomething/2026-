# 2026-02-26 UIUX Issue #340 Matchup Title Policy Report (Runtime Target Sync)

## 1) 이슈
- issue: #340 `[UIUX][P1] 매치업 상세 제목 정책 개편(선거명 우선, 기사제목 부제)`
- 목표: 매치업 상세 상단 제목을 canonical 선거명(지역+선거유형)으로 고정하고, 기사형 제목은 부제로 분리
- PM 추가 요구(2026-02-26): 런타임 타깃 파일 기준(`apps/web/app/matchups/[matchup_id]/page.js`)으로 반영

## 2) 구현 내용
1. 런타임 타깃 파일에 canonical title 정책 반영
- 파일: `apps/web/app/matchups/[matchup_id]/page.js`
- `region_code + office_type` 기반 canonical 타이틀 생성
- Hero `h1`을 `matchup.title`이 아닌 canonical 타이틀로 고정

2. 기사형 제목 부제 분리
- Hero 본문에 `기사 제목: {article_headline}` 라인 추가
- 조사기관/조사기간 라인은 별도 유지

3. office_type/region_code 라벨 보강
- code형 office_type(`metro_mayor`, `metro_council`, `local_mayor` 등) + 한글 office_type 모두 대응
- `KR-11`~`KR-39` prefix 기반 광역 라벨 맵 적용

4. 라우트 충돌 제거
- 중복 라우트였던 `apps/web/app/matchups/[matchup_id]/page.tsx` 삭제
- Next 라우팅이 런타임 타깃 `page.js`를 사용하도록 정리

## 3) 변경 파일
- `apps/web/app/matchups/[matchup_id]/page.js` (수정)
- `apps/web/app/matchups/[matchup_id]/page.tsx` (삭제)

## 4) 증빙
1. before/after 1:1 비교 (desktop)
- before(runtime): `UIUX_reports/screenshots/2026-02-26_issue340_runtime_before_desktop.png`
- after(local runtime-target): `UIUX_reports/screenshots/2026-02-26_issue340_runtime_after_local_desktop_v2.png`

2. before/after 1:1 비교 (mobile)
- before(runtime): `UIUX_reports/screenshots/2026-02-26_issue340_runtime_before_mobile.png`
- after(local runtime-target): `UIUX_reports/screenshots/2026-02-26_issue340_runtime_after_local_mobile_v2.png`

## 5) 검증
- `cd apps/web && npm run build` PASS (2026-02-26 재실행)
- 매치업 라우트 충돌 해소 확인(`page.tsx` 제거 후 `page.js` 단일 라우트)
- 본 이슈 변경 범위(매치업 상세 제목 정책)는 런타임 화면 캡처로 확인 완료

## 6) 수용기준 매핑
- 제목 canonical 고정: 충족
- 기사 제목 부제 분리: 충족
- 런타임 반영 파일 기준 수정: 충족(`page.js`)

## 7) 현재 상태
- issue #340 라벨은 PM 지시대로 `status/blocked` 유지
- blocker: 운영 배포 실패(Vercel) 및 #352 선행 이슈 의존으로 운영 URL after 증빙 미확보

## 8) PR
- active PR: `https://github.com/iAmSomething/2026-/pull/355`

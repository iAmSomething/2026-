# 2026-02-18 Issue #28 CI Secret Preflight Report

## 1) 이슈
- 대상: `#28 [DEVELOP] CI Secret Preflight 도입(누락/오설정 조기차단)`
- 목표: secret 누락/오형식으로 인한 CI 실패를 사전 차단

## 2) 구현 사항
1. 공통 preflight 스크립트
- 파일: `scripts/qa/preflight_required_secrets.sh`
- 기능:
  - 필수 secret 존재 검사
  - 형식 검사 (`SUPABASE_URL`, `DATABASE_URL`, `INTERNAL_JOB_TOKEN`)
  - 누락/오류 시 fail-fast + 수정 가이드 출력

2. 워크플로 적용 (2개 이상 충족)
- `.github/workflows/staging-smoke.yml`
- `.github/workflows/phase1-qa.yml`
- `.github/workflows/ingest-schedule.yml`

3. 문서 표준 목록 갱신
- `README.md`에 CI 필수 secret 목록 추가
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`의 preflight 섹션 반영

4. PM Cycle secret health 검토 반영
- 파일: `scripts/pm/pm_cycle_dry_run.sh`
- 반영:
  - `## Secret Health (Review)` 섹션 추가
  - 권한 허용 시 필수 secret 누락 요약
  - 권한 부족 시 `unavailable`로 안전하게 표기

## 3) 검증
1. preflight 실패 케이스
- 실행: 빈 환경에서 `scripts/qa/preflight_required_secrets.sh`
- 결과: 누락 secret 목록 및 가이드 출력 후 실패

2. preflight 성공 케이스
- 실행: 더미 유효 형식 env 주입 후 실행
- 결과: 필수 항목 통과 및 `[PASS] Required secrets preflight passed`

3. 워크플로 적용 검증
- `Phase1 QA` 성공: [run 22145184714](https://github.com/iAmSomething/2026-/actions/runs/22145184714)
- `Staging Smoke` 성공: [run 22145184703](https://github.com/iAmSomething/2026-/actions/runs/22145184703)

## 4) 완료기준 대비
1. 최소 2개 워크플로 적용
- 충족 (3개 적용)

2. 누락 secret 원인 메시지 명확
- 충족 (스크립트 fail-fast 가이드 출력)

3. develop_report 제출
- 충족 (본 문서)

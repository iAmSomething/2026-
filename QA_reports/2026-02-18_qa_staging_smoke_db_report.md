# QA Staging Smoke DB 실패 수정 검증 보고서

- Date: 2026-02-18
- Issue: #27
- Related Issue: #29
- Status: PASS
- Report-Path: `QA_reports/2026-02-18_qa_staging_smoke_db_report.md`

## 1) 검증 목표
- Staging Smoke에서 발생하던 DB 연결 실패 수정 결과를 QA 기준으로 재현 검증한다.
- `workflow_dispatch`(수동) 1회 + `push`(자동) 1회 성공을 확인한다.

## 2) 재현/검증 실행
1. 선행 실패(원인 기준선)
- Run: https://github.com/iAmSomething/2026-/actions/runs/22144074304
- Event: `push`
- Result: `failure`

2. 수동 실행 확인
- Run: https://github.com/iAmSomething/2026-/actions/runs/22145452995
- Event: `workflow_dispatch`
- Head: `80596ee3ab58fabd981f81c46a2ca23cc7a4b0f1`
- Result: `success`

3. 자동 실행 확인
- Run: https://github.com/iAmSomething/2026-/actions/runs/22145449865
- Event: `push`
- Head: `80596ee3ab58fabd981f81c46a2ca23cc7a4b0f1`
- Result: `success`

## 3) 기대결과 vs 실제결과
- Expected:
  - `DATABASE_URL` secret 부재 상황에서도 fallback postgres로 스모크 파이프라인이 완료되어야 한다.
  - API/Web 기동 및 핵심 스모크 체크가 모두 통과해야 한다.
- Actual:
  - 수동/자동 실행 모두 성공(`success`).
  - `Run staging smoke checks` 단계까지 통과 확인.

## 4) 원인 진단 및 수정 근거
- 원인 분류: 환경/부트스트랩(Secret 의존)
- 수정 근거 파일:
  - `.github/workflows/staging-smoke.yml`
  - `scripts/qa/preflight_required_secrets.sh`
- QA 회귀 체크리스트 반영:
  - `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`의 스모크 검증 항목에
    `DATABASE_URL secret 부재 시 workflow fallback postgres 연결 정상 동작` 추가

## 5) 판정
- [QA PASS]
- #27 완료기준 충족:
  - QA 보고서 제출 완료
  - 수동 1회 + 자동 1회 성공 실행 확인
  - PASS 코멘트 및 링크 첨부 가능

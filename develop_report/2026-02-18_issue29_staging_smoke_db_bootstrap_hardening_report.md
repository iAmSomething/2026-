# 2026-02-18 Issue #29 Staging Smoke DB Bootstrap Hardening Report

## 1) 이슈
- 대상: `#29 [DEVELOP] Staging Smoke DB 연결 실패 수정(DATABASE_URL/부트스트랩 하드닝)`
- 원인: `DATABASE_URL` secret 누락 시 CI에서 빈 문자열로 실행되어 `psycopg.OperationalError` 발생

## 2) 조치 내용
1. `staging-smoke` DB 부트스트랩 강화
- 파일: `.github/workflows/staging-smoke.yml`
- 반영:
  - workflow service postgres 추가 (`postgres:16`)
  - `DATABASE_URL` secret 비어 있을 때 fallback URL(`postgresql://postgres:postgres@127.0.0.1:5432/app`) 자동 주입
  - DB readiness wait 단계 추가

2. Secret preflight 단계 도입
- 파일: `.github/workflows/staging-smoke.yml`
- 반영:
  - `scripts/qa/preflight_required_secrets.sh` 호출
  - 누락/형식 오류 시 fail-fast

3. 초기화 스크립트 에러 메시지 개선
- 파일: `scripts/init_db.py`
- 반영:
  - `DATABASE_URL` 비어있을 때 즉시 가이드 출력
  - DB 연결 실패 시 원인/수정 가이드 출력

## 3) 검증 결과
1. 실패 재현 이력(원인 확인)
- `Staging Smoke` 실패: [run 22144074304](https://github.com/iAmSomething/2026-/actions/runs/22144074304)

2. 수정 후 성공 실행
- `Staging Smoke` 성공: [run 22145184703](https://github.com/iAmSomething/2026-/actions/runs/22145184703)
- 보조 성공 실행: [run 22145013143](https://github.com/iAmSomething/2026-/actions/runs/22145013143)

## 4) 완료기준 대비
1. `Staging Smoke` 1회 이상 green
- 충족

2. DB 연결 오류 재발 방지
- 충족 (`DATABASE_URL` fallback + preflight + readiness wait)

3. develop_report 제출
- 충족 (본 문서)

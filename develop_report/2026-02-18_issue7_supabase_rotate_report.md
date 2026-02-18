# 이슈 #7 보고서: Supabase service_role 키 rotate 실행/재주입 검증

- 이슈: https://github.com/iAmSomething/2026-/issues/7
- 작성일: 2026-02-18
- 담당: develop

## 1. 수행 범위
1. rotate 전 사전 점검
2. Secret 재주입 후 검증 절차 정의 및 실행 준비
3. 권한 의존 작업(실제 rotate) 분리

## 2. 사전 점검 결과
1. 현재 service key 유효성 점검
- `valid key -> /rest/v1/ status 200`
- `invalid key -> /rest/v1/ status 401`
- 결과: 현재 키는 활성 상태로 확인

2. 코드/문서 기준 Secret 계약 확인
- 필수 환경변수: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATA_GO_KR_KEY`, `DATABASE_URL`
- 운영 문서에 rotate 절차 반영 확인:
  - `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
  - `docs/05_RUNBOOK_AND_OPERATIONS.md`

## 3. rotate 후 재주입 검증 절차(실행 체크리스트)
1. 오너가 Supabase Dashboard에서 `service_role` rotate 수행
2. 새 키를 Secret Manager 및 `.env`(로컬 테스트용)에 반영
3. 아래 검증 실행
- 새 키: `/rest/v1/` 호출 시 200
- 구 키: `/rest/v1/` 호출 시 401
- 백엔드 헬스/쿼리 정상

## 4. 상태
- 구현/문서/테스트 준비 완료
- 실제 rotate 실행은 오너 권한 필요로 대기

## 5. 요청 사항
- 오너가 rotate 완료 시점 공유 필요
- 공유 후 develop에서 재주입 검증 로그를 추가 제출하고 이슈 종료 가능

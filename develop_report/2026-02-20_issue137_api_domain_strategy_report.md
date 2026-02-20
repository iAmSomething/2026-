# 2026-02-20 Issue #137 API Domain Strategy Report

## 1. 결정사항
1. 단기(즉시): 운영 API 기준값은 `https://2026-api-production.up.railway.app` 유지
2. 중기(베타/운영 직전): 커스텀 도메인 `https://api.<your-domain>`로 1회 컷오버

## 2. 결정 근거
1. 현재 기준 도메인은 실측 smoke/CORS/웹 라우트 연동이 검증되어 안정 운영 상태
2. 커스텀 도메인 전환은 벤더 종속 완화, 주소 안정성, 대외 신뢰성 측면에서 필요
3. 지금 즉시 전환보다, 운영 안정 유지 후 계획된 1회 컷오버가 리스크 최소화

## 3. 반영 파일
1. `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
2. `docs/05_RUNBOOK_AND_OPERATIONS.md`
3. `develop_report/2026-02-20_issue137_api_domain_strategy_report.md`

## 4. 문서 반영 내용
1. 배포 문서에 API 도메인 전략 섹션 추가
- 현재 기준 도메인 유지 원칙
- 커스텀 도메인 전환 시점/완료 기준
- 실패 시 롤백 기준
2. 운영 런북에 커스텀 도메인 컷오버 절차 추가
- DNS -> Railway Domain/TLS -> Vercel env 변경 -> 재배포 -> smoke 검증

## 5. 후속 이슈
1. 생성: `#137 [DEVELOP] API 커스텀 도메인 전환(api.<domain>) 실행`
2. 라벨: `role/develop`, `type/task`, `priority/p1`, `status/backlog`
3. 담당: `iAmSomething`

## 6. 의사결정 요청(Owner)
1. 실제 사용할 운영 도메인 확정
- 예: `api.2026election.kr` 또는 `api.<보유도메인>`
2. 컷오버 실행 윈도우 확정
- 권장: 트래픽 낮은 시간대 30분 윈도우

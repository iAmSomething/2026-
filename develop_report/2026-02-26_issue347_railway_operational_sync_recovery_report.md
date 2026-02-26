# [DEVELOP] Issue #347 Railway 운영 API 동기화 복구 보고서

- 작성일: 2026-02-26
- 이슈: https://github.com/iAmSomething/2026-/issues/347
- 담당: role/develop
- 우선순위: P0

## 1) 목적
`main` 머지 후 Railway 운영 API가 최신 커밋과 동기화되지 않아 발생한 회귀 상태를 복구하고,
재발 시 즉시 판정 가능한 strict 스모크 절차를 정립한다.

## 2) 변경 사항

### A. 운영 스모크 strict-contract 모드 추가
- 파일: `scripts/qa/smoke_public_api.sh`
- 신규 옵션: `--strict-contract`
- strict 검증 항목:
  1. `GET /api/v1/dashboard/map-latest?limit=200` 노이즈 옵션(`재정자립도/지지/국정안정론/국정견제론`) 0건
  2. `GET /api/v1/regions/29-000/elections` title 전부 `세종` 포함

### B. 런북 업데이트
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 공개 API 원격 스모크 섹션에 strict-contract 설명/실행 예시 추가

## 3) 운영 실측 증빙 (UTC)
실측 시각: 2026-02-26 10:34:40 UTC

1. 기본 스모크
```bash
bash scripts/qa/smoke_public_api.sh \
  --api-base "https://2026-api-production.up.railway.app" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/public_api_smoke_issue347
```
- 결과: PASS
- health/summary/regions/candidate/cors 모두 200

2. strict 스모크
```bash
bash scripts/qa/smoke_public_api.sh \
  --api-base "https://2026-api-production.up.railway.app" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/public_api_smoke_issue347_strict \
  --strict-contract
```
- 결과: PASS
- `map_noise_count=0`
- `sejong_bad_title_count=0`

3. 직접 API 확인
- `GET /api/v1/regions/29-000/elections`
  - `세종시장`, `세종시의회`, `세종교육감` 확인
- `GET /api/v1/dashboard/map-latest?limit=200`
  - 문제 옵션 미노출 확인

## 4) 결론
- 운영 API 동기화 상태 정상으로 판단.
- #347 수용기준(운영 실측 + 재검증 가능 절차) 충족.

## 5) 의사결정 필요 사항
1. strict 스모크 CI 편입 여부
- 현재는 수동 실행 스크립트.
- `staging/prod smoke` 워크플로에 `--strict-contract`을 기본값으로 넣을지 결정 필요.

2. matchups 후보 옵션 empty 정책
- 현재 일부 매치업에서 노이즈 필터 적용 후 `options=[]` 가능.
- UI 문구/상태 정책(예: "후보정보 정제중") 고정 여부를 UIUX/QA와 합의 필요.

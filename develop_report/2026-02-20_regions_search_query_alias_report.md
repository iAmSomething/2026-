# 2026-02-20 Regions Search Query Alias Report

## 1. 목적
- `GET /api/v1/regions/search`가 `q`와 `query` 파라미터를 모두 허용하도록 API 호환성을 보강한다.

## 2. 반영 파일
1. `app/api/routes.py`
2. `tests/test_api_routes.py`
3. `scripts/qa/smoke_public_api.sh`
4. `docs/05_RUNBOOK_AND_OPERATIONS.md`
5. `develop_report/2026-02-20_regions_search_query_alias_report.md`

## 3. 구현 상세
1. `regions/search`에서 `q`를 우선 사용
2. `q`가 없으면 query string의 `query` 값을 fallback으로 사용
3. 둘 다 없으면 `422` 반환
4. 원격 스모크 스크립트의 지역검색 호출을 `q` 기준으로 정렬

## 4. 검증
1. 단위 테스트
```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q tests/test_api_routes.py -k "api_contract_fields"
```
- 결과: `1 passed`

2. 공개 API 원격 스모크
```bash
scripts/qa/smoke_public_api.sh \
  --api-base https://2026-production.up.railway.app \
  --web-origin https://2026-deploy.vercel.app \
  --out-dir /tmp/regions_alias_public_smoke
```
- 결과:
  - `health=200`
  - `summary=200`
  - `regions=200`
  - `candidate=200`
  - `cors=200`
  - `cors_allow_origin=https://2026-deploy.vercel.app`

## 5. 결론
- `regions/search`는 `q`/`query` 양쪽 호출을 처리 가능해졌고, 현재 공개 웹/공개 API 스모크 경로와 일치한다.

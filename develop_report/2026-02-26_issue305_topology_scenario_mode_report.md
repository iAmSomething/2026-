# 2026-02-26 DEVELOP P1 선거체계 시나리오 모드(official/scenario) 지원 보고서 (#305)

## 1) 작업 범위
1. topology 버전 관리 스키마 추가
2. 지역 선거 슬롯 조회 API에 topology/version 파라미터 추가
3. scenario 모드에서 광주·전남 통합 슬롯 시뮬레이션 지원
4. 운영 안전장치 유지(기본 official)

## 2) 핵심 변경
1. DB 스키마 확장
   - `region_topology_versions(version_id, mode, effective_from, effective_to, status, note)`
   - `region_topology_edges(parent_region_code, child_region_code, version_id)`
   - mode/status 체크 제약 및 인덱스 추가
   - 기본 seed 추가:
     - `official-v1`
     - `scenario-gj-jn-merge-v1`
     - edges: `29-46-000 <- 29-000, 46-000`
2. API 계약 확장
   - `GET /api/v1/regions/{region_code}/elections?topology=official|scenario&version_id=...`
   - 기본값은 `topology=official`
3. repository 로직 확장 (`fetch_region_elections`)
   - topology/version 해석
   - scenario에서 child->parent edge 적용
   - parent region 미존재 시 child regions 기반 synthetic region 생성
   - 슬롯 응답에 topology 메타 포함:
     - `topology`, `topology_version_id`
4. UI 검색 페이지 연동
   - topology/version query 전달 유지
   - scenario/placeholder 상태에서도 슬롯 리스트 렌더 유지

## 3) 변경 파일
1. `/Users/gimtaehun/election2026_codex/db/schema.sql`
2. `/Users/gimtaehun/election2026_codex/app/services/repository.py`
3. `/Users/gimtaehun/election2026_codex/app/models/schemas.py`
4. `/Users/gimtaehun/election2026_codex/app/api/routes.py`
5. `/Users/gimtaehun/election2026_codex/apps/web/app/search/page.js`
6. `/Users/gimtaehun/election2026_codex/tests/test_api_routes.py`
7. `/Users/gimtaehun/election2026_codex/tests/test_repository_region_elections_master.py`
8. `/Users/gimtaehun/election2026_codex/tests/test_schema_region_topology.py` (신규)

## 4) 검증
1. 부분 검증:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_repository_region_elections_master.py tests/test_api_routes.py tests/test_schema_region_topology.py
```
2. 전체 회귀:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q
```
3. 결과: `180 passed in 2.70s`

## 5) 수용 기준 대비
1. topology 파라미터에 따라 슬롯 구성 변화: 완료
2. official 기본동작 회귀 0: 완료(전체 테스트 통과)
3. scenario 모드 광주·전남 통합 슬롯 시뮬레이션: 완료

## 6) 의사결정 필요
1. scenario synthetic region 표시명 확정 필요
   - 현재: `광주·전남 통합특별시` 기반 자동 생성
2. scenario 전용 버전 라이프사이클 운영정책 확정 필요
   - `draft/announced/effective` 전환 책임자 및 전환 절차(runbook) 명시 필요

# 2026-02-27 Runtime Candidate Noise Denylist Hotfix Report

## 1) 작업 개요
- 대상 이슈: `#488` `[DEVELOP][P0][HOTFIX] 운영 API 후보 비인명 토큰 즉시 차단 가드`
- 배경: 운영 `matchups` 응답에서 비인명 토큰(예: `최고치`, `접촉률은`, `엔비디아`, `가격`)이 후보 옵션으로 노출.
- 목표: collector 재처리 전까지 API runtime에서 즉시 차단 + 후보 0건 시 fail-safe 동작.

## 2) 구현 변경 사항
1. 후보 토큰 차단 규칙 강화 (`/app/services/candidate_token_policy.py`)
- 운영 실측 노이즈 토큰/패턴 denylist 확장.
- 후처리 룰 추가:
  - `...보다` / `...는데도` 형태 문장조각 차단.
- `matchup`/`map-latest` 모두 동일 정책 함수 기반으로 차단 적용.

2. matchup fail-safe 추가 (`/app/services/repository.py`)
- `get_matchup()`에서 noise 필터 이후 후보가 0건일 때:
  - `has_data=false`, `scenarios=[]`, `options=[]` 반환 유지
  - `needs_manual_review=true`로 승격
  - `review_queue`에 `mapping_error`를 pending으로 1회 등록(중복 pending/in_progress 방지)
- `ensure_review_queue_pending()` 추가(중복 삽입 방지 헬퍼).

3. 관측 메트릭 노출 (`/app/models/schemas.py`, `/app/services/repository.py`)
- 응답 필드 `candidate_noise_block_count` 추가.
- 해당 matchup 처리 중 runtime에서 차단된 후보 토큰 수를 노출.

## 3) 테스트/검증
1. 단위/통합 테스트
- 실행:
  - `pytest -q tests/test_candidate_token_policy_runtime_hotfix.py tests/test_repository_matchup_scenarios.py tests/test_map_latest_cleanup_policy.py tests/test_api_routes.py -k "matchup or map_latest or candidate_token_policy_runtime_hotfix"`
- 결과: `18 passed`

2. 실DB 코드 검증 (로컬 코드 + 운영 DB)
- `PostgresRepository.get_matchup('20260603|광역자치단체장|11-000')`
- 결과:
  - `has_data=false`
  - `needs_manual_review=true`
  - `candidate_noise_block_count=7`
  - `option_names=[]`

3. map-latest 검증 (로컬 API 실행)
- `/api/v1/dashboard/map-latest?limit=200`에서 `region_code=11-000`
- 결과: 정상 인명 후보(`정원오`) 유지 확인.

## 4) 수용 기준 매핑
- [x] 운영 API에서 비인명 토큰 노출 0 (코드 기준 핫픽스 적용)
- [x] 정상 인명 후보 유지
- [x] 임시가드 적용 사실 보고서 제출

## 5) 의사결정 필요 사항
- 없음.

## 6) 변경 파일
- `/app/services/candidate_token_policy.py`
- `/app/services/repository.py`
- `/app/models/schemas.py`
- `/tests/test_candidate_token_policy_runtime_hotfix.py`
- `/tests/test_repository_matchup_scenarios.py`
- `/tests/test_map_latest_cleanup_policy.py`
- `/tests/test_api_routes.py`
- `/develop_report/2026-02-27_runtime_candidate_noise_denylist_hotfix_report.md`

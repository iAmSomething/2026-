# 2026-02-27 Issue461 Matchup Recent Observation Fallback Report

## 배경
- 후보 토큰 정리 이후 일부 매치업에서 최신 관측치의 후보 옵션이 전부 필터링되어 `options=[]`이 발생할 수 있음.
- 이 경우 최신값만 고정 조회하면 사용자 화면에 유의미한 후보 지표가 사라질 수 있음.

## 구현
1. 최근 관측치 다건 조회 추가
- 파일: `app/services/repository.py`
- 함수: `_fetch_recent_matchup_observations(matchup_id, limit=5)`
- 기존 최신 1건 조회에서 최근 최대 5건 조회로 확장

2. matchup 응답 선택 로직 개선
- 파일: `app/services/repository.py`
- 함수: `get_matchup`
- 동작:
  - 최신 -> 과거 순으로 순회
  - `_normalize_options` 결과가 비어있지 않은 첫 관측치를 선택
  - 전부 비어있으면 기존처럼 빈 시나리오/옵션 유지(`has_data=false`)

3. 테스트 추가
- 파일: `tests/test_repository_matchup_scenarios.py`
- 케이스:
  - 최신 관측치 무효/직전 관측치 유효 시 직전 관측치로 폴백
  - 최근 관측치 모두 무효 시 `has_data=false`, `options=[]`, `scenarios=[]`

## 검증
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_matchup_scenarios.py tests/test_repository_matchup_legal_metadata.py`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py -k matchup`
- 결과:
  - `6 passed`
  - `4 passed, 30 deselected`

## 영향
- `GET /api/v1/matchups/{matchup_id}`에서 최신 1건 고정 조회로 인한 빈 옵션 노출을 완화.
- 데이터 품질 가드와 사용자 가시성의 균형을 맞춰, 가능한 경우 직전 유효 후보 구도를 제공.

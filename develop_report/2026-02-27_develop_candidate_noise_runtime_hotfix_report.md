# 2026-02-27 Develop Candidate Noise Runtime Hotfix Report

## 배경
- 사용자 운영 화면에서 후보별 최신 지표에 비후보 토큰(예: `대비`)이 노출되는 케이스 확인.
- `#364`(collector 검증기 운영 반영) 이후에도 과거 적재 레코드 중 `candidate_verified=true`, `candidate_verify_source=manual` 조합이 남아 노출될 수 있음.

## 조치 요약
1. 후보명 잡음 토큰 사전 보강
- 파일: `app/services/candidate_token_policy.py`
- 추가 차단 토큰:
  - exact/substr: `대비`, `박빙`, `접전`, `우세`, `열세`, `경합`, `혼전`, `선두`

2. 저장소 응답 정규화에 수동검증 저품질 행 차단
- 파일: `app/services/repository.py`
- 신규 함수: `_is_low_quality_manual_candidate_option(row)`
- 차단 조건:
  - `candidate_verify_source == manual`
  - `candidate_id`가 synthetic(`cand:` prefix)
  - 정당 정보 미확정
  - `candidate_verify_matched_key`가 후보명 힌트와 동일(실질 검증 근거 없음)
  - `candidate_verify_confidence >= 0.95`
- 적용 지점:
  - `PostgresRepository._normalize_options()`에서 noise 토큰 필터 다음 단계로 제외.

3. 회귀 테스트 추가
- 파일: `tests/test_repository_matchup_scenarios.py`
  - `대비` 토큰 차단 케이스 추가
  - 수동검증 저품질 행 차단 단위 테스트 추가
- 파일: `tests/test_map_latest_cleanup_policy.py`
  - map latest에서 `대비` 제외 케이스 추가

## 검증 결과
- 실행:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_matchup_scenarios.py tests/test_map_latest_cleanup_policy.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py -k 'map_latest or matchup'`
- 결과:
  - `5 passed`
  - `6 passed, 28 deselected`

## 영향 범위
- `GET /api/v1/matchups/{matchup_id}` 후보 옵션 정규화
- `GET /api/v1/dashboard/map-latest` 후보명 유효성 제외 정책

## 남은 운영 작업(권장)
1. 기존 DB 레거시 레코드 정리
- 런타임 필터로 즉시 노출은 줄이지만, 원본 데이터 클린업(재검증/재적재)이 병행되면 품질 안정성이 높음.

2. QA 재게이트
- `#376` 후보자명 유효성 QA 팩에서 동일 hotspot 재확인 필요.

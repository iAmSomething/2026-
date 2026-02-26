# 2026-02-26 Issue #282 Option Type Classifier Report

## 1. 대상 이슈
- Issue: #282 `[COLLECTOR][P0] 옵션 타입 엄밀화: 국정평가 vs 선거성격 분류기`
- URL: https://github.com/iAmSomething/2026-/issues/282

## 2. 구현 요약
- `presidential_approval` 입력을 정규화 단계에서 분기:
  - `president_job_approval`: 대통령 직무/국정수행 평가 신호
  - `election_frame`: 국정안정/정부견제/선거성격 신호
- 모호 문항은 자동 분류하지 않고 `needs_manual_review=true`로 유지.
- ingest 단계에서 모호 문항을 `review_queue(issue_type=mapping_error)`로 자동 라우팅.
- 대시보드 요약 쿼리는 신/구 타입을 모두 조회하도록 확장.
- API 요약 응답은 신타입(`president_job_approval`, `election_frame`)을 우선 반영하고, `presidential_approval`는 deprecated 호환 필드로 유지.

## 3. 변경 파일
- 코드
  - `app/services/ingest_input_normalization.py`
  - `app/services/ingest_service.py`
  - `app/services/repository.py`
  - `app/api/routes.py`
  - `scripts/generate_collector_live_coverage_v2_pack.py`
- 테스트
  - `tests/test_normalize_ingest_payload_for_schedule.py`
  - `tests/test_ingest_service.py`
  - `tests/test_api_routes.py`
  - `tests/test_collector_live_coverage_v2_pack_script.py`
- 데이터 샘플/아티팩트
  - `data/sample_ingest.json`
  - `data/sample_ingest_article_cutoff_filtered.json`
  - `data/collector_freshness_hotfix_v1_payload.json`
  - `data/collector_live_coverage_v2_payload.json`
  - `data/collector_live_coverage_v2_report.json`

## 4. 검증 결과
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_normalize_ingest_payload_for_schedule.py tests/test_ingest_service.py tests/test_repository_dashboard_summary_scope.py tests/test_collector_live_coverage_v2_pack_script.py`
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py`
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_ingest_adapter.py`
- 결과:
  - `18 passed`
  - `15 passed`
  - `1 passed`

## 5. 산출물 상태
- `collector_live_coverage_v2_report.json` 기준:
  - `option_type_counts.party_support = 2`
  - `option_type_counts.election_frame = 2`
  - `option_type_counts.presidential_approval = 0`
  - `acceptance_checks` 전체 `true`

## 6. 수용 기준 대비
1. 동일 기사에서 국정평가 문항/선거성격 문항 분리 저장
- 충족: 분류 규칙 코드 반영 + ingest/API 테스트 추가

2. `국정안정론/국정견제론`가 `president_job_approval`로 저장되지 않음
- 충족: 샘플/아티팩트 `election_frame` 전환 확인

3. 모호 문항은 수동검토 라우팅
- 충족: `needs_manual_review=true` + `review_queue(issue_type=mapping_error)` 테스트 검증

## 7. 의사결정 필요사항
1. `presidential_approval` deprecated 필드 제거 시점 확정 필요
- 현재는 API 하위호환을 위해 유지했습니다.
- 제거 릴리즈(버전/날짜) 확정 시, QA/스크립트(`smoke`, `contract suite`) 키셋도 함께 정리 가능합니다.

2. 이슈 본문의 `collector_summary_nonempty_*` 보정 파일 반영 범위 확인 필요
- 현재 `#282` 브랜치에는 해당 파일이 존재하지 않아, 동일 계열의 active 샘플/운영 payload(`sample_ingest*`, `collector_live_coverage_v2_payload`, `collector_freshness_hotfix_v1_payload`)를 우선 정리했습니다.

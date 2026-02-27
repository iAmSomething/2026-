# 2026-02-27 Issue #359 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#359` `[COLLECTOR][P1] 2026 지방선거 데이터셋 시간 게이트 강화(2025-12-01 이후)`
- 목표: 2025-12-01 이전 사이클 데이터가 ingest/노출 경로에 섞이지 않도록 시간 게이트를 강제하고, map-latest 필터 통계에 `stale_cycle` 집계를 노출.

## 2) 반영 내용
- `app/services/cutoff_policy.py`
  - `SURVEY_END_DATE_CUTOFF = 2025-12-01` 추가
  - `parse_date_like`, `survey_end_date_cutoff_reason`, `is_survey_end_date_allowed` 추가
- `app/services/ingest_service.py`
  - ingest 시작 시 `survey_end_date` 컷오프 동시 검증 추가
  - 기준 미달 시 `ingestion_error` + `STALE_CYCLE_BLOCK reason=SURVEY_END_DATE_BEFORE_CUTOFF`로 review_queue 기록 후 skip
- `app/api/routes.py`
  - `_is_cutoff_eligible_row`에 `survey_end_date` 컷오프 동시 적용
  - summary/map-latest/big-matches/matchup 노출 경로에서 동일 게이트 적용
  - map-latest `filter_stats.reason_counts`에서 컷오프 계열 사유를 `stale_cycle`로 통합 집계

## 3) 테스트 반영
- `tests/test_cutoff_policy.py`
  - survey_end 컷오프 파싱/판정 케이스 추가
- `tests/test_ingest_service.py`
  - `survey_end_date < 2025-12-01` 레코드 ingest 차단 테스트 추가
- `tests/test_api_routes.py`
  - summary에서 survey_end 컷오프 필터 테스트 추가
  - big-matches에서 survey_end 컷오프 필터 테스트 추가
  - map-latest `reason_counts.stale_cycle` 집계 테스트 추가
  - matchup survey_end 컷오프 시 404 테스트 추가

## 4) 검증 결과
- 실행 명령:
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_cutoff_policy.py tests/test_ingest_service.py tests/test_api_routes.py -q`
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_collector_map_latest_cleanup_v1_script.py -q`
- 결과:
  - `50 passed`
  - `1 passed`

## 5) 증적 파일
- before/after 분포 캡처:
  - `data/issue359_time_gate_before_after_distribution.json`
- 재적재 1회 probe:
  - `data/issue359_reingest_cutoff_probe.json`

핵심 확인값:
- summary: `before=3`, `after=1`, `excluded_stale_cycle=2`
- map-latest: `reason_counts.stale_cycle=2`
- big-matches: `before=3`, `after=1`, `excluded_stale_cycle=2`
- reingest probe: `processed_count=1`, `error_count=1`, old-cycle는 `STALE_CYCLE_BLOCK`으로 차단

## 6) 수용기준 대응
- 운영 노출 경로(summary/map-latest/big-matches)에서 2025-12-01 이전 건 차단 로직 반영
- map-latest `filter_stats.reason_counts`에 `stale_cycle` 집계 반영
- 게이트 온/오프 경계 회귀 테스트 추가 및 PASS
- 재적재 1회 증적 + before/after 분포 증적 제출 완료

## 7) 의사결정 요청
1. `stale_cycle` 상세 원인(`article_published_at_before_cutoff` vs `survey_end_date_before_cutoff`)을 API 응답에서 추가 노출할지 여부 결정 필요.
2. 현재 cutoff 기준일 `2025-12-01`을 상수로 고정했습니다. 운영 전환 시 환경변수(`DATASET_CYCLE_CUTOFF`)로 외부화할지 결정 필요.

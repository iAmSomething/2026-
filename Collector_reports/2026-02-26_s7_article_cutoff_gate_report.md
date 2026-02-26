# [COLLECTOR][P0] #272 기사 시점 컷오프 고정 보고서

## 1) 작업 개요
- 이슈: `#272 [COLLECTOR][P0] 기사 시점 컷오프 고정(2025-12-01 이후만 허용)`
- 목표: `published_at >= 2025-12-01T00:00:00+09:00` 고정 정책을 discovery/ingest/API 노출 경로에 반영하고, backfill cleanup 실행 SQL과 증빙 산출물 제공.

## 2) 반영 범위
- 단일 정책 소스 추가
  - `app/services/cutoff_policy.py`
  - 컷오프 상수: `ARTICLE_PUBLISHED_AT_CUTOFF_ISO = 2025-12-01T00:00:00+09:00`
- discovery 게이트 반영
  - `src/pipeline/discovery_v11.py`
  - 기사 `published_at`가 컷오프 이전이면 `mapping_error`로 review_queue 라우팅 후 제외
  - 메트릭 추가: `cutoff_excluded_count`
- ingest 게이트 반영
  - `app/services/ingest_service.py`
  - `article` 소스 레코드에 대해 컷오프 이전 `published_at` 차단
  - 차단 건은 `ingestion_error`로 review_queue 기록
- API 노출 보호 반영
  - `app/api/routes.py`
  - summary/map-latest/big-matches/matchup 응답에서 컷오프 이전 기사 기반 행 제외
- backfill cleanup 증빙/실행 템플릿 추가
  - `scripts/generate_collector_article_cutoff_cleanup_v1.py`
  - 필터링 payload + report 생성, DB cleanup SQL 템플릿 동봉

## 3) 테스트 결과
- 실행:  
  `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_cutoff_policy.py tests/test_discovery_v11.py tests/test_ingest_service.py tests/test_api_routes.py tests/test_collector_article_cutoff_cleanup_v1_script.py`
- 결과: `33 passed`

## 4) 산출물 및 증빙
- 코드
  - `app/services/cutoff_policy.py`
  - `src/pipeline/discovery_v11.py`
  - `app/services/ingest_service.py`
  - `app/api/routes.py`
  - `scripts/generate_collector_article_cutoff_cleanup_v1.py`
- 테스트
  - `tests/test_cutoff_policy.py`
  - `tests/test_discovery_v11.py`
  - `tests/test_ingest_service.py`
  - `tests/test_api_routes.py`
  - `tests/test_collector_article_cutoff_cleanup_v1_script.py`
- 데이터 증빙
  - `data/collector_article_cutoff_cleanup_v1_report.json`
  - `data/collector_article_cutoff_cleanup_v1_report_live30.json`
  - `data/sample_ingest_article_cutoff_filtered.json`
  - `data/collector_live_news_v1_payload_30_article_cutoff_filtered.json`

## 5) 완료 기준 점검
- 새 ingest에서 컷오프 이전 데이터 적재 0건:
  - ingest 단계 차단 로직 반영 완료 (`app/services/ingest_service.py`)
- API 노출 컷오프 위반 0건:
  - dashboard/matchup 응답 레이어 필터 반영 완료 (`app/api/routes.py`)
- 기존 데이터 정리(backfill cleanup):
  - 삭제/정리 SQL 템플릿 제공 완료 (`data/collector_article_cutoff_cleanup_v1_report*.json` 내 `backfill_cleanup_sql`)

## 6) 의사결정 요청
- 정책 해석 확인 필요:
  - 현재 정책은 `published_at`이 존재하는 경우에만 컷오프 이전을 차단합니다.
  - `published_at` 미기재(`null`) 기사도 차단 대상으로 확장할지 확정 요청.
  - 확정 시 `cutoff_policy.py` 기준으로 strict 모드(`null`도 차단) 즉시 전환 가능.

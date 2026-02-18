# 2026-02-18 Issue #32 Ops Metrics API Report

## 1) 이슈
- 대상: `#32 [DEVELOP] 운영 지표 대시보드용 ingest/review 메트릭 API 추가`
- 목표: PM/QA 운영 관제를 위한 ingest/review 지표 요약 JSON 제공

## 2) 구현 내용
1. 운영 지표 API 추가
- 엔드포인트: `GET /api/v1/ops/metrics/summary`
- 파라미터: `window_hours` (기본 24, 1~336)

2. 집계 쿼리 추가
- 파일: `app/services/repository.py`
- 추가 메서드:
  - `fetch_ops_ingestion_metrics`
  - `fetch_ops_review_metrics`
  - `fetch_ops_failure_distribution`
- 집계 대상:
  - `ingestion_runs` 상태/처리량/오류량/실패율
  - `review_queue` 상태/24시간 이상 pending/`mapping_error` 카운트
  - `review_queue.issue_type` 분포

3. 응답 스키마 추가
- 파일: `app/models/schemas.py`
- 추가 모델:
  - `OpsIngestionMetricsOut`
  - `OpsReviewMetricsOut`
  - `OpsFailureDistributionOut`
  - `OpsWarningRuleOut`
  - `OpsMetricsSummaryOut`

4. 경고 규칙 정의 (3개)
- `fetch_fail_rate > 0.15`
- `mapping_error_24h_count >= 5`
- `pending_over_24h_count >= 10`

5. 운영 문서 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 반영:
  - 내부 운영 API 목록에 지표 API 추가
  - 지표 API 확인 절차 추가
  - 경고 규칙 섹션 추가

## 3) 검증
1. 테스트
- `pytest`: 47 passed

2. 실제 지표 조회 샘플
- 파일: `data/ops_metrics_summary_sample.json`
- 결과: HTTP 200, 집계/분포/경고 규칙 포함

## 4) 완료기준 대비
1. 지표 조회 1회 성공 + 샘플 결과 첨부
- 충족 (`data/ops_metrics_summary_sample.json`)

2. 경고 규칙 2개 이상 정의
- 충족 (3개 정의)

3. develop_report 제출
- 충족 (본 문서)

# 2026-02-19 Issue #35 Review Queue Ops API Report

## 1) 이슈
- 대상: `#35 [DEVELOP] review_queue 운영 API(목록/통계) 확장`
- 목표: 운영자가 review_queue를 목록/통계/추세 관점에서 즉시 확인 가능한 API와 문서/샘플을 제공

## 2) 구현 내용
1. review_queue 운영 API 3종 추가
- 파일: `app/api/routes.py`
- 추가 엔드포인트:
  - `GET /api/v1/review-queue/items`
  - `GET /api/v1/review-queue/stats`
  - `GET /api/v1/review-queue/trends`

2. 응답 스키마 추가
- 파일: `app/models/schemas.py`
- 추가 모델:
  - `ReviewQueueItemOut`
  - `ReviewQueueIssueCountOut`
  - `ReviewQueueErrorCountOut`
  - `ReviewQueueStatsOut`
  - `ReviewQueueTrendPointOut`
  - `ReviewQueueTrendsOut`

3. 집계/조회 쿼리 추가
- 파일: `app/services/repository.py`
- 추가 메서드:
  - `fetch_review_queue_items`
  - `fetch_review_queue_stats`
  - `fetch_review_queue_trends`
- 지원 필터:
  - 목록: `status`, `issue_type`, `assigned_to`, `limit`, `offset`
  - 추세: `window_hours`, `bucket_hours`, `issue_type`, `error_code`

4. PM/QA 요약 JSON 포맷 문서화
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 추가 내용:
  - 내부 운영 API 목록에 review_queue API 3종 반영
  - `8.4 PM/QA 요약 JSON 포맷` 섹션 신설(통계/추세 예시 및 필드 해석 규칙)

5. 샘플 fixture 추가
- `data/review_queue_stats_sample.json`
- `data/review_queue_trends_sample.json`

6. 계약 스위트 확장
- 파일: `scripts/qa/run_api_contract_suite.sh`
- 변경:
  - 8-endpoint 안내 문구 -> 11-endpoint로 갱신
  - review_queue 3개 API success/empty 케이스 추가

7. README 반영
- 파일: `README.md`
- 변경:
  - 공개 API 개수 `8 -> 11`
  - review_queue 3개 API 목록 추가
  - 계약 스위트 설명 `API 11종`으로 업데이트

## 3) 검증
1. 단위 테스트
- 명령: `.venv/bin/pytest -q`
- 결과: `49 passed`

2. API 계약 스위트
- 명령: `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue35.json`
- 결과: `total=25, pass=25, fail=0`
- 산출물: `data/qa_api_contract_report_issue35.json`

## 4) 완료기준 대비
1. API 2개 이상 추가 및 동작 검증
- 충족 (3개 추가 + pytest/contract suite 통과)

2. 운영자가 바로 읽을 수 있는 요약 포맷 제공
- 충족 (`docs/05_RUNBOOK_AND_OPERATIONS.md` 8.4 섹션 + 샘플 fixture)

3. develop_report 1건 제출
- 충족 (본 문서)

## 5) 의사결정 필요사항
1. `error_code` 모델링 방식 확정 필요
- 현재는 `review_queue.issue_type`를 `major:code` 형식으로 해석해 `error_code`를 계산합니다.
- 선택지:
  - A안: 현행 유지 (`issue_type` 문자열 규약)
  - B안: `review_queue.error_code` 컬럼을 별도로 추가해 집계 정확도/쿼리 단순화

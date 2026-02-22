# 2026-02-22 W1 review queue ops api v1 report

## 1. 요약
- 이슈: `#173 [DEVELOP][W1] review_queue 운영 API v1`
- 목표: 검수 승인/반려 운영 API를 추가하고 인증/응답 계약/런북을 정비

## 2. 구현
1. 신규 API
- `POST /api/v1/review/{item_id}/approve`
- `POST /api/v1/review/{item_id}/reject`
- 인증: `Authorization: Bearer $INTERNAL_JOB_TOKEN`

2. 입력/출력 계약
- 입력: `ReviewQueueDecisionIn`
  - `assigned_to`(optional)
  - `review_note`(optional)
- 출력: `ReviewQueueItemOut` (갱신된 review_queue row)

3. 저장소 로직
- `app/services/repository.py`
  - `update_review_queue_status(...)` 추가
  - status/assigned_to/review_note/updated_at 갱신 + row 반환

4. 라우팅
- `app/api/routes.py`
  - approve/reject 엔드포인트 추가
  - 없는 item_id는 404 반환

5. 문서
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 내부 운영 API 목록에 approve/reject 추가
  - 호출 예시/인증/응답 정책 추가

## 3. 검증
1. 테스트
- 실행: `.venv313/bin/python -m pytest tests/test_api_routes.py -q`
- 결과: `10 passed`
- 포함 검증:
  - missing token -> 401
  - invalid token -> 403
  - approve/reject -> 200 + 상태 갱신
  - 없는 항목 -> 404

2. 샘플 응답
- `data/verification/issue173_review_api_sample.json`
- `data/verification/issue173_review_api_curl.log`
- `data/verification/issue173_review_api_pytest.log`

## 4. DoD 체크
- [x] 구현/설계/검증 반영
- [x] 보고서 제출
- [x] 이슈 코멘트에 report_path/evidence/next_status 기재 예정

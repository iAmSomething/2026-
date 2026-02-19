# 운영 런북 및 체크리스트

- 문서 버전: v0.2
- 최종 수정일: 2026-02-18
- 수정자: Codex

## 1. 운영 목표
- 2시간 주기의 안정적인 데이터 수집/정규화/검증/게시
- 자동 처리와 수동 검수 경계를 명확히 유지

## 2. 배치 운영 절차 (2시간 주기)
1. 수집 시작: 기사 후보 수집
2. 판별: 여론조사 기사 여부 분류
3. 추출: 수치/문항/후보/지역 추출
4. 정규화: 값/코드/식별자 통일
5. 검증: 공식/신뢰 데이터 대조
6. 게시: 통과 데이터만 공개 API 반영
7. 기록: `ingestion_runs` 결과 저장

## 2.1 자동 실행 경로 (2시간)
1. GitHub Actions 스케줄 워크플로: `.github/workflows/ingest-schedule.yml`
2. 주기: `0 */2 * * *` (UTC 기준 2시간 간격)
3. 실행 방식:
- 워크플로가 API 서버(`uvicorn`)를 기동
- `scripts/qa/run_ingest_with_retry.py`로 `POST /api/v1/jobs/run-ingest` 호출
- 결과 리포트 `data/ingest_schedule_report.json` 아티팩트 업로드
4. 필수 Secret:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATA_GO_KR_KEY`
- `DATABASE_URL`
- `INTERNAL_JOB_TOKEN`

## 3. 수동/자동 경계
### 자동 처리
1. 중복 제거
2. 규칙 추출
3. 정규화
4. 명확 일치 검증 결과 게시

### 수동 검수 필요
1. 후보명/지역명 충돌
2. 동일 조사 수치 불일치
3. 원문 근거 부족 또는 문맥 모호
4. 코드 매핑 실패

## 4. 검수 워크플로우
1. 검수 큐 조회 (`status=pending`)
2. 이슈 타입 확인 (`mapping_error`, `value_conflict`, `source_conflict`)
3. 승인 또는 반려
4. 반려 시 사유 템플릿 기록
5. 승인 데이터 재게시

## 5. 내부 운영 API
1. 수동 배치 실행: `POST /api/v1/jobs/run-ingest`
2. 운영 지표 요약: `GET /api/v1/ops/metrics/summary`
3. 커버리지 지표 요약: `GET /api/v1/ops/coverage/summary`
4. 검수 큐 목록: `GET /api/v1/review-queue/items`
5. 검수 큐 통계: `GET /api/v1/review-queue/stats`
6. 검수 큐 추세: `GET /api/v1/review-queue/trends`

## 6. 장애 대응
1. 수집 실패:
- 네트워크 상태 확인
- 재시도 큐 실행
2. 파싱 실패:
- 원문 저장 여부 확인
- 파서 규칙 업데이트
3. DB 실패:
- 연결 상태 점검
- 트랜잭션 롤백 확인
4. API 응답 이상:
- 헬스체크
- 직전 배포 버전 롤백

## 6.1 재시도 운영 규칙
1. 내부 배치 호출 실패(네트워크/5xx/partial_success) 시 최대 2회 재시도
2. 재시도 간 backoff: 1초, 2초
3. 최종 실패 시:
- 실행 리포트(`ingest_schedule_report.json`) 확인
- `review_queue` 적재 여부 확인
- `ingestion_runs`에서 `partial_success`/오류 카운트 확인

## 7. 재처리 운영
1. 기간 지정 재처리
2. 소스 지정 재처리
3. 검수 반영 후 부분 재집계
4. 재처리 이력 `ingestion_runs`에 분리 기록

## 8. 모니터링 체크리스트
1. 배치 성공률
2. 기사 수집량 대비 추출 성공률
3. 검수 큐 적체량
4. 공개 API 오류율/지연시간
5. 키 만료/쿼터 초과 알림

## 8.1 운영 SLO/KPI
1. 추출 품질 KPI: 핵심 수치 추출 Precision >= 0.90 (샘플 100건 수동 검수)
2. 배치 안정성 KPI: 7일 연속 정기 배치 성공
3. 검수 처리 KPI: `pending` 24시간 초과 건수 최소화

## 8.2 지표 API 확인 절차
1. `GET /api/v1/ops/metrics/summary?window_hours=24` 호출
2. 확인 항목:
- `ingestion.total_runs/success_runs/failed_runs`
- `ingestion.fetch_fail_rate`
- `review_queue.pending_over_24h_count`
- `failure_distribution` 상위 `issue_type`
3. `GET /api/v1/ops/coverage/summary` 호출
4. 확인 항목:
- `state` (`ready|partial|empty`)
- `warning_message`
- `regions_total`
- `regions_covered`
- `sido_covered`
- `observations_total`
- `latest_survey_end_date`
5. 해석 기준:
- `ops/coverage/summary` 값은 기본적으로 누적 집계(cumulative)이며, 기간 필터 없이 전체 커버리지 상태를 표시한다.
6. 상태 규칙:
- `empty`: `observations_total == 0`
- `partial`: 데이터는 있으나 `regions_covered < regions_total` 또는 `regions_total` 기준 미확보
- `ready`: `regions_total > 0` 이고 `regions_covered >= regions_total`

## 8.3 경고 규칙 (기본값)
1. `fetch_fail_rate > 0.15` 이면 경고
2. `mapping_error_24h_count >= 5` 이면 경고
3. `pending_over_24h_count >= 10` 이면 경고

## 8.4 PM/QA 요약 JSON 포맷
1. 검수 큐 통계 요약 (`GET /api/v1/review-queue/stats`)
```json
{
  "generated_at": "2026-02-18T15:30:00Z",
  "window_hours": 24,
  "total_count": 12,
  "pending_count": 5,
  "in_progress_count": 3,
  "resolved_count": 4,
  "issue_type_counts": [
    {"issue_type": "ingestion_error", "count": 6},
    {"issue_type": "mapping_error:region_not_found", "count": 3}
  ],
  "error_code_counts": [
    {"error_code": "region_not_found", "count": 3},
    {"error_code": "unknown", "count": 9}
  ]
}
```
2. 검수 큐 추세 요약 (`GET /api/v1/review-queue/trends`)
```json
{
  "generated_at": "2026-02-18T15:30:00Z",
  "window_hours": 24,
  "bucket_hours": 6,
  "points": [
    {
      "bucket_start": "2026-02-18T12:00:00Z",
      "issue_type": "mapping_error",
      "error_code": "region_not_found",
      "count": 2
    }
  ]
}
```
3. 필드 해석 규칙
- `issue_type`은 `review_queue.issue_type`의 대분류(콜론 이전 값)를 사용
- `error_code`는 `review_queue.issue_type`의 세부코드(콜론 이후 값)이며 없으면 `unknown`
- `generated_at`은 API 생성 시각(UTC)이고, `bucket_start`도 UTC 기준으로 해석

## 9. 일일 운영 체크
1. 새벽 배치 실패 여부
2. 검수 큐 24시간 초과 항목 여부
3. 빅매치 계산 결과 이상치 여부
4. 지도 데이터 누락 지역 여부

## 10. 준법 체크
1. robots 정책 위반 요청 로그 여부
2. 기사 원문 저장 모드가 최소 스팬 기본값으로 유지되는지 확인
3. 외부 공개 시 출처 URL/근거 표기가 누락되지 않았는지 확인

## 11. 키 회전 운영 (D0)
1. `service_role` 키가 파일/로그/메신저에 노출되면 즉시 비상 회전
2. Supabase Dashboard > Project Settings > API에서 `service_role` rotate
3. 기존 키 폐기 확인 후 새 키만 Secret Manager에 저장
4. `.env`, `supabase_info.txt`, 실행 로그에 구키/신키 출력 금지

## 11.1 회전 후 자동 검증 (스크립트)
1. 아래 환경변수 준비:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (신키)
- `OLD_SUPABASE_SERVICE_ROLE_KEY` (선택, 구키)
2. 검증 실행:
```bash
REPORT_FILE=develop_report/rotation_verify_latest.md \
SUPABASE_URL=... \
SUPABASE_SERVICE_ROLE_KEY=... \
OLD_SUPABASE_SERVICE_ROLE_KEY=... \
bash scripts/qa/verify_supabase_service_role_rotation.sh
```
3. 판정 기준:
- 신키 상태코드 `200` 필수
- 구키 제공 시 상태코드 `200`이면 실패(폐기 미완료)
4. 결과 파일(`REPORT_FILE`)을 이슈 코멘트에 `Report-Path`로 연결

## 12. 실행 산출물 관리 정책
1. 입력 데이터 JSON(`data/bootstrap_ingest_coverage_v1.json` 등)은 재현성 보장을 위해 Git 추적 유지
2. 실행 산출물 JSON(`*_apply_report.json`, `*_issue*.json`)은 기본적으로 Git 비추적
3. PM 주기 리포트(`reports/pm/*`)는 로컬/CI 임시 산출물로 취급하고 Git 추적 금지
4. 실행 증빙은 Actions artifact 또는 이슈 코멘트 링크로 공유

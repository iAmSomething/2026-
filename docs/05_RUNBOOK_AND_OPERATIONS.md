# 운영 런북 및 체크리스트

- 문서 버전: v0.2
- 최종 수정일: 2026-02-19
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
5. 상대시점 정책 플래그:
- `RELATIVE_DATE_POLICY` (`strict_fail` 기본, `allow_estimated_timestamp` 선택)

## 2.2 Workflow Lint Guard (PR Fail-Fast)
1. 대상 워크플로: `.github/workflows/workflow-lint-guard.yml`
2. 트리거: Pull Request에서 `.github/workflows/*.yml|*.yaml` 변경 시 자동 실행
3. 검사 단계:
- `bash scripts/qa/validate_workflow_yaml.sh`로 YAML 파싱 오류 즉시 차단
- `rhysd/actionlint@v1`로 GitHub Actions 문법/표현식 검증
4. 로컬 사전 점검:
- `bash scripts/qa/validate_workflow_yaml.sh`
5. 깨진 샘플 재현(테스트 브랜치):
- `.github/workflows/` 내 임시 파일에 들여쓰기 오류를 넣고 PR 생성
- `Workflow Lint Guard`가 실패하는지 확인 후 임시 파일 제거

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
4. 운영 품질 요약: `GET /api/v1/dashboard/quality`
5. 검수 큐 목록: `GET /api/v1/review-queue/items`
6. 검수 큐 통계: `GET /api/v1/review-queue/stats`
7. 검수 큐 추세: `GET /api/v1/review-queue/trends`
8. 검수 승인: `POST /api/v1/review/{item_id}/approve` (Bearer token)
9. 검수 반려: `POST /api/v1/review/{item_id}/reject` (Bearer token)

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

## 6.2 상대시점 변환 운영 규칙
1. 기본 정책 `strict_fail`:
- 기사에 상대시점(예: 어제/지난주)이 있고 `article.published_at`가 없으면 `survey_end_date`를 비워두고 review_queue 라우팅
2. 선택 정책 `allow_estimated_timestamp`:
- `article.published_at` 결측 시 `article.collected_at` 기반 추정값 허용
- `date_inference_mode='estimated_timestamp'` 저장, review_queue 라우팅
3. 불확실 추론(`date_inference_confidence < 0.8`)은 정책과 무관하게 review_queue 라우팅
4. 옵션 정당 추론에서 `party_inferred=true`이면서 `party_inference_confidence < 0.8`이면
- `review_queue.issue_type='party_inference_low_confidence'`로 라우팅

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

## 7.1 검수 승인/반려 운영
1. 승인 호출:
- `POST /api/v1/review/{item_id}/approve`
- body 예시: `{ "assigned_to": "ops.user", "review_note": "근거 확인 완료" }`
2. 반려 호출:
- `POST /api/v1/review/{item_id}/reject`
- body 예시: `{ "review_note": "근거 부족" }`
3. 인증:
- `Authorization: Bearer $INTERNAL_JOB_TOKEN`
4. 응답:
- 최신 `review_queue` row를 반환하며 `status`가 `approved|rejected`로 갱신된다.

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
- `ingestion.date_inference_failed_count`
- `ingestion.date_inference_estimated_count`
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
7. `GET /api/v1/dashboard/quality` 호출
8. 확인 항목:
- `freshness_p50_hours`, `freshness_p90_hours`
- `official_confirmed_ratio`
- `needs_manual_review_count`
- `source_channel_mix.article_ratio`, `source_channel_mix.nesdc_ratio`
- `quality_status`
- `freshness.status`, `freshness.over_24h_ratio`, `freshness.over_48h_ratio`
- `official_confirmation.status`, `official_confirmation.unconfirmed_count`
- `review_queue.pending_count`, `review_queue.in_progress_count`, `review_queue.pending_over_24h_count`
9. 품질 해석 기준:
- percentile 값이 `null`이면 관측치 부족 상태로 간주
- `official_confirmed_ratio` 하락 또는 `needs_manual_review_count` 급증 시 QA/수집기 재점검 트리거

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
5. `dashboard/summary`의 `scope_breakdown.regional/local/unknown`가 0인지 확인(전국 오염 방지)
6. `dashboard/summary`/`dashboard/map-latest`/`dashboard/big-matches`의 `freshness_hours`와 `source_priority` 확인(공식확정 지연 감시)

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

## 13. 커버리지 배치 v2 적용 절차
1. 적용 입력:
- `data/bootstrap_ingest_coverage_v2.json`
2. 적용 실행(동일 입력 2회 적용):
```bash
python -m app.jobs.bootstrap_ingest --input data/bootstrap_ingest_coverage_v2.json --report data/bootstrap_ingest_coverage_v2_apply_report.json
python -m app.jobs.bootstrap_ingest --input data/bootstrap_ingest_coverage_v2.json --report data/bootstrap_ingest_coverage_v2_apply_report.json
```
3. 전후 비교 산출:
- `data/bootstrap_ingest_coverage_v2_before_after.json`
- 확인 항목:
  - `delta_v1_to_v2.regions_covered`
  - `delta_v1_to_v2.sido_covered`
  - `delta_v1_to_v2.observations_total`
4. idempotent 판정:
- `idempotent_check.delta.regions_covered == 0`
- `idempotent_check.delta.sido_covered == 0`
- `idempotent_check.delta.observations_total == 0`

## 14. 웹 RC 체크리스트 (Issue #123)
1. 준비 변수:
```bash
WEB_URL="https://2026-deploy.vercel.app"
API_BASE="https://2026-api-production.up.railway.app"
```
2. URL 접근(200) 확인:
```bash
curl -sS -o /tmp/web_rc_home.html -w "%{http_code}\n" "$WEB_URL"
```
3. 홈 렌더 핵심 문자열 확인:
```bash
rg -n "Election 2026 Staging|API Base|summary fetch failed" /tmp/web_rc_home.html
```
4. API 3개 연동 확인(200 기대):
```bash
curl -sS -o /tmp/web_rc_summary.json -w "%{http_code}\n" "$API_BASE/api/v1/dashboard/summary"
curl -sS -o /tmp/web_rc_regions.json -w "%{http_code}\n" "$API_BASE/api/v1/regions/search?q=%EC%84%9C%EC%9A%B8"
curl -sS -o /tmp/web_rc_candidate.json -w "%{http_code}\n" "$API_BASE/api/v1/candidates/cand-jwo"
```
5. fallback/오류 표시 확인:
- `summary fetch failed`가 보이면 web이 정상적으로 오류 fallback을 렌더링한 상태다.
- 스테이징/공개 환경 기본값은 `https://2026-api-production.up.railway.app`이며, 장애 시 fallback 오류 문구를 확인한다.
6. 내부 운영 API 토큰 정책 유지:
- `/api/v1/jobs/*`는 `Authorization: Bearer <INTERNAL_JOB_TOKEN>` 필수
- `/api/v1/review/*` 계열 엔드포인트도 토큰 필수 정책 유지

## 15. 공개 API 원격 스모크 (Railway)
1. 스크립트:
- `scripts/qa/smoke_public_api.sh`
2. 기본 타깃:
- `API_BASE=https://2026-api-production.up.railway.app`
- `WEB_ORIGIN=https://2026-deploy.vercel.app`
3. 검증 항목:
- `GET /health` (200)
- `GET /api/v1/dashboard/summary` (200)
- `GET /api/v1/regions/search?q=서울` (200, `query` alias도 허용)
- `GET /api/v1/candidates/cand-jwo` (200 또는 계약된 404)
- CORS preflight(`OPTIONS /api/v1/dashboard/summary`) 응답 및 `access-control-allow-origin` 일치
4. 실행 예시:
```bash
scripts/qa/smoke_public_api.sh \
  --api-base "https://2026-api-production.up.railway.app" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/public_api_smoke
```

## 16. 공개 웹 라우트 RC 스모크
1. 대상 URL:
- `https://2026-deploy.vercel.app/`
- `https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor`
- `https://2026-deploy.vercel.app/candidates/cand-jwo`
2. 확인 명령:
```bash
for u in \
  "https://2026-deploy.vercel.app/" \
  "https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor" \
  "https://2026-deploy.vercel.app/candidates/cand-jwo"; do
  curl -sS -o /tmp/$(echo "$u" | tr '/:.' '_').html -w "$u -> %{http_code}\n" "$u"
done
```
3. 판정:
- 3개 URL이 모두 `200`이면 PASS
- `404`가 하나라도 나오면 Vercel 프로젝트 루트(`apps/web`) 및 최신 배포 상태를 우선 점검
4. 매치업 ID 정합화 참고:
- 공개 웹 라우트 `/matchups/m_2026_seoul_mayor`는 API alias 매핑으로 canonical `matchup_id`(`20260603|광역자치단체장|11-000`)를 조회한다.

## 17. API 커스텀 도메인 컷오버 런북 (Issue #137)
1. 사전 고정:
- 현재 기준 API: `https://2026-api-production.up.railway.app`
- 목표 API: `https://api.<your-domain>`
2. 순서:
- DNS(CNAME/TXT) 검증 완료
- Railway Custom Domain 연결 + TLS 발급 완료
- API CORS allowlist에 `https://2026-deploy.vercel.app` 유지 확인
- Vercel 환경변수(`API_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`)를 목표 API로 교체
- Vercel 재배포 후 웹/API 스모크 재실행
3. 검증 명령:
```bash
NEW_API_BASE="https://api.<your-domain>"
scripts/qa/smoke_public_api.sh \
  --api-base "$NEW_API_BASE" \
  --web-origin "https://2026-deploy.vercel.app" \
  --out-dir /tmp/public_api_smoke_custom_domain
```
4. 성공 판정:
- `/health`, summary/regions/candidate, CORS preflight 모두 200
- `https://2026-deploy.vercel.app/`, `/matchups/m_2026_seoul_mayor`, `/candidates/cand-jwo` 모두 200
5. 실패/롤백:
- 실패 시 Vercel env를 기존 `https://2026-api-production.up.railway.app`로 즉시 복구
- 복구 후 동일 스모크로 200 재확인

## 18. 공개 웹 Baseline 파라미터 시나리오 (Issue #148)
1. 대상 URL:
- `https://2026-deploy.vercel.app/?scope_mix=1`
- `https://2026-deploy.vercel.app/?selected_region=KR-11`
- `https://2026-deploy.vercel.app/search?demo_query=%EC%97%B0%EC%88%98%EA%B5%AD`
- `https://2026-deploy.vercel.app/search?demo_query=%EC%97%86%EB%8A%94%EC%A7%80%EC%97%AD%EB%AA%85`
- `https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor?confirm_demo=article&source_demo=article&demo_state=ready`
- `https://2026-deploy.vercel.app/matchups/m_2026_seoul_mayor?confirm_demo=official&source_demo=nesdc&demo_state=ready`
- `https://2026-deploy.vercel.app/candidates/cand-jwo?party_demo=inferred&confirm_demo=article`
- `https://2026-deploy.vercel.app/candidates/cand-jwo?party_demo=official&confirm_demo=official`
- `https://2026-deploy.vercel.app/candidates/cand-does-not-exist?party_demo=inferred&confirm_demo=official`
2. 판정 포인트:
- Home: `scope_mix` 경고/배지 노출, `selected_region` 선택 상태 반영
- Search: alias 보정(`연수국 -> 연수구`)과 empty-state 대체 액션 노출
- Matchup: `confirm_demo`/`source_demo`/`demo_state` 배지와 상태 카피 노출
- Candidate: `party_demo`/`confirm_demo` 배지 노출, 미존재 후보 ID는 안전 fallback으로 렌더 유지

## 15. 무인 오케스트레이션 운영
1. 디스패치:
- 워크플로: `autonomous-dispatch.yml`
- 트리거: 30분 스케줄 + 수동 실행
- 정책: `status/ready` 이슈를 역할별 파이프라인으로 자동 전달

2. 워치독:
- 워크플로: `automation-watchdog.yml`
- 정책: `PM Cycle`과 `Ingest Schedule` 최근 실행 간격이 임계치를 넘으면 자동 self-heal dispatch

3. 기본 임계값:
- `PM_MAX_IDLE_MINUTES=70`
- `INGEST_MAX_IDLE_MINUTES=150`
- `AUTO_DISPATCH_MAX=2`

4. 장애 시 확인 순서:
1. `Automation Watchdog` 최근 런 결과
2. `Autonomous Dispatch`의 dispatched/skipped 수
3. 대상 워크플로(`PM Cycle`, `Ingest Schedule`) 최근 런 링크 확인

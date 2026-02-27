# 배포 및 개발 환경 명세

- 문서 버전: v0.2
- 최종 수정일: 2026-02-19
- 수정자: Codex

## 1. 최종 배포 아키텍처
1. DB: Supabase Postgres
2. API/배치: FastAPI (Python)
3. 웹 프론트: Next.js
4. 권장 배포 경로:
- 웹: Vercel
- API/배치: Railway
- DB/스토리지: Supabase

## 2. 컴포넌트 책임
1. Supabase
- 정규화 데이터 저장
- 접근 제어(RLS)
- 백업/모니터링
2. FastAPI
- 공개 API 제공
- 기사 수집/추출/검증 배치 실행
- 검수용 내부 API 제공
3. Next.js
- 대시보드/검색/상세 UI 렌더링
- API 데이터 시각화

## 3. 개발 환경 원칙 (가상환경 필수)
1. 로컬 Python 패키지는 프로젝트 가상환경(`.venv`)에서만 설치/실행
2. 시스템 Python 전역 설치 금지
3. Python `3.13` 고정 권장 (`3.14`는 `pydantic-core` 빌드 이슈 가능)
4. 실행 예시:
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. 비밀키 정책
1. `key.txt`는 로컬 전용 파일
2. `key.txt` 절대 커밋 금지 (`.gitignore` 반영)
3. 운영에서는 플랫폼 Secret으로 주입
4. `.env` 파일도 커밋 금지
5. `service_role` 키 노출 이력 발생 시 즉시 rotate:
- Supabase Dashboard > Project Settings > API > `service_role` rotate
- 기존 키 폐기 후 새 키만 플랫폼 Secret에 저장
- 로컬 `supabase_info.txt`는 참고용으로만 보관하고 코드/로그 출력 금지

## 5. Data.go.kr API 활용 설계
### 필수
1. `CommonCodeService`
2. `PofelcddInfoInqireService`

### CommonCodeService 동기화 스크립트
1. 스크립트: `scripts/sync_common_codes.py`
2. 권장 환경변수:
- `DATA_GO_KR_KEY`
- `COMMON_CODE_REGION_URL`
- `COMMON_CODE_SIGUNGU_URL` (선택: 시군구 분리 endpoint 사용 시)
- `COMMON_CODE_PARTY_URL`
- `COMMON_CODE_ELECTION_URL`
3. 실행 예시:
```bash
PYTHONPATH=. .venv/bin/python scripts/sync_common_codes.py \
  --region-url "$COMMON_CODE_REGION_URL" \
  --region-sigungu-url "$COMMON_CODE_SIGUNGU_URL" \
  --party-url "$COMMON_CODE_PARTY_URL" \
  --election-url "$COMMON_CODE_ELECTION_URL" \
  --elections-report-path "data/elections_master_sync_report.json"
```
4. 산출 리포트: `data/common_codes_sync_report.json`
- `diff.added_count`, `diff.updated_count`, `diff.delete_candidate_count` 포함
- 실패 시 `status=failed` + `review_queue(issue_type=code_sync_error)` 기록
5. elections 마스터 슬롯 동기화:
- `sync_common_codes.py` 실행 시 기본적으로 `scripts/sync_elections_master.py`가 연쇄 실행
- 분리 실행도 가능:
```bash
PYTHONPATH=. .venv/bin/python scripts/sync_elections_master.py \
  --report-path "data/elections_master_sync_report.json"
```

### 선택
1. `WinnerInfoInqireService2`
2. `VoteXmntckInfoInqireService2`
3. `PartyPlcInfoInqireService`

## 6. 네트워크/보안
1. 프론트는 공개 API만 접근
2. 내부 운영 API는 별도 토큰/권한으로 분리
3. 관리자 승인 API는 서버-서버 통신만 허용
4. API CORS 허용 오리진:
- `https://2026-deploy.vercel.app` (운영 고정)

## 7. 배포 전략
1. `main` 기준 자동 배포
2. 배포 전 체크:
- 마이그레이션 적용 가능 여부
- 필수 Secret 주입 여부
- 공개 API 헬스체크
3. 롤백:
- API 컨테이너 이전 버전 롤백
- DB는 롤백 SQL 또는 스냅샷 복구 기준 운영

## 8. 스테이징 실행 경로 (Issue #26 기준)
1. 목적:
- FastAPI + Next.js + Supabase(Postgres) 최소 E2E 검증
2. 기본 URL/포트:
- API: `http://127.0.0.1:8100`
- Web: `http://127.0.0.1:3300`
3. 필수 환경변수 계약:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATA_GO_KR_KEY`
- `DATABASE_URL`
- `INTERNAL_JOB_TOKEN`
4. 선택 환경변수:
- `RELATIVE_DATE_POLICY` (`strict_fail` 기본, `allow_estimated_timestamp` 선택)
- `API_READ_CACHE_TTL_SEC` (초 단위, 기본 `0`=비활성, 권장 `15~30`)
4. CI 부트스트랩 전략:
- `DATABASE_URL` secret가 비어 있으면 workflow service postgres(`postgresql://postgres:postgres@127.0.0.1:5432/app`)로 자동 fallback
- secret preflight는 fallback 반영 후 실행되어 DB URL 누락 원인을 즉시 표시
5. CI 파이프라인:
- Workflow: `.github/workflows/staging-smoke.yml`
- Web app path: `apps/staging-web`
- 흐름: schema 적용 -> 샘플 적재 -> API/Web 기동 -> 스모크 검증

## 9. 스모크 테스트 기준
1. 스크립트: `scripts/qa/smoke_staging.sh`
2. 검증 항목:
- `GET /health`
- `POST /api/v1/jobs/run-ingest` (Bearer 토큰)
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/regions/search`
- `GET /api/v1/candidates/{candidate_id}`
- `GET /` (Next.js 홈)
- `DATABASE_URL` secret 부재 시 workflow fallback postgres 연결 정상 동작
3. 실행 예시:
```bash
API_BASE=http://127.0.0.1:8100 \
WEB_BASE=http://127.0.0.1:3300 \
INTERNAL_JOB_TOKEN=replace-me \
scripts/qa/smoke_staging.sh --api-base "$API_BASE" --web-base "$WEB_BASE"
```

## 10. Secret 주입/로그 마스킹 정책 (스테이징)
1. Secret은 GitHub Actions Secrets로만 주입한다.
2. 값 출력 금지:
- `SUPABASE_SERVICE_ROLE_KEY`
- `INTERNAL_JOB_TOKEN`
- `DATABASE_URL` 원문 비밀번호
3. 로그 검증:
- 스모크 스크립트에서 로그 파일을 대상으로 `sb_secret_` 등 민감 패턴 스캔
- 탐지 시 실패 처리

## 11. CI Secret Preflight
1. 스크립트: `scripts/qa/preflight_required_secrets.sh`
2. 적용 워크플로:
- `.github/workflows/staging-smoke.yml`
- `.github/workflows/phase1-qa.yml`
- `.github/workflows/ingest-schedule.yml`
3. 필수 GitHub Repository Secrets:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATA_GO_KR_KEY`
- `DATABASE_URL`
- `INTERNAL_JOB_TOKEN`
4. 동작:
- 누락 secret 발견 시 fail-fast
- 형식 오류(`SUPABASE_URL`, `DATABASE_URL`, `INTERNAL_JOB_TOKEN`)에 대해 즉시 가이드 출력

## 12. Vercel Preview CI (Issue #92)
1. Workflow:
- `.github/workflows/vercel-preview.yml` (`workflow_dispatch`)
2. 배포 원칙:
- 배포 타깃은 `Vercel`
- 토큰은 GitHub Repository Secret으로만 주입
3. 필수 Secrets:
- `VERCEL_TOKEN`
- `VERCEL_SCOPE` (team slug)
- `VERCEL_PROJECT_NAME`
4. Dispatch 입력:
- `root_dir`: `apps/web` (공개 도메인 배포 단일 소스 경로)
- `issue_number`: URL 코멘트를 남길 이슈 번호(실행 시 명시 입력)
5. 실행 결과:
- Preview URL 추출 후 `issue_number`에 코멘트 자동 작성
- 접근 검증(`curl`) 로그와 배포 로그를 artifact로 업로드
- Preview 접근정책은 `public` 고정이며 `401`이면 실패 처리한다.

## 13. 웹 확인용 RC 고정값 (Issue #123)
1. 공개 확인 URL(Production):
- `https://2026-deploy.vercel.app`
2. 배포 기준 브랜치:
- `main` (GitHub Deployment Production ref 기준)
3. RC 배포 설정:
- 타깃: `Vercel`
- 프로젝트 루트 단일 기준: `apps/web` (공개 도메인 배포 소스 경로)
- 배포 입력값은 GitHub Secrets(`VERCEL_TOKEN`, `VERCEL_SCOPE`, `VERCEL_PROJECT_NAME`)으로만 주입
- Preview/Production 공통 API base 고정값: `https://2026-api-production.up.railway.app`
4. 공개 라우트 RC 확인 대상:
- `/`
- `/matchups/m_2026_seoul_mayor`
- `/candidates/cand-jwo`
5. 웹 API endpoint 환경변수 계약:
- 코드 기준: `apps/web/app/_lib/api.js`
- 해석 우선순위: `API_BASE_URL` -> `NEXT_PUBLIC_API_BASE_URL` -> `https://2026-api-production.up.railway.app`
- 개발(local) 권장:
  - `API_BASE_URL=http://127.0.0.1:8100`
  - `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8100`
- 스테이징/공개 확인 권장:
  - `NEXT_PUBLIC_API_BASE_URL=https://2026-api-production.up.railway.app`
  - 필요 시 `API_BASE_URL`도 동일 값으로 주입
6. fallback 동작:
- 스테이징/공개 환경에서 API Base env가 비어 있어도 Railway 공개 URL을 fallback으로 사용한다.

## 14. API 도메인 전략 (Issue #137)
1. 현재 운영 기준:
- `https://2026-api-production.up.railway.app`
- 이유: 실배포 응답(health/API/CORS) 검증 완료 상태로 즉시 안정 운영 가능
2. 전환 전략:
- 베타/운영 직전에 1회 커스텀 도메인(`api.<your-domain>`)으로 컷오버
- 컷오버 전까지는 기존 Railway 생성 도메인을 기준값으로 유지
3. 컷오버 완료 기준:
- Railway Custom Domain + TLS 활성화
- Vercel env(`API_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`) 신규 도메인 반영
- 공개 API smoke 200 및 공개 웹 3개 URL 200 재검증
4. 롤백 기준:
- 컷오버 후 API/CORS 실패 시 즉시 env를 `https://2026-api-production.up.railway.app`로 복귀

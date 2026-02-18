# 배포 및 개발 환경 명세

- 문서 버전: v0.2
- 최종 수정일: 2026-02-18
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
- `COMMON_CODE_PARTY_URL`
- `COMMON_CODE_ELECTION_URL`
3. 실행 예시:
```bash
PYTHONPATH=. .venv/bin/python scripts/sync_common_codes.py \
  --region-url "$COMMON_CODE_REGION_URL" \
  --party-url "$COMMON_CODE_PARTY_URL" \
  --election-url "$COMMON_CODE_ELECTION_URL"
```

### 선택
1. `WinnerInfoInqireService2`
2. `VoteXmntckInfoInqireService2`
3. `PartyPlcInfoInqireService`

## 6. 네트워크/보안
1. 프론트는 공개 API만 접근
2. 내부 운영 API는 별도 토큰/권한으로 분리
3. 관리자 승인 API는 서버-서버 통신만 허용

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

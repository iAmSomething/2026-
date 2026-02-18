# 개발 보고서: 백엔드 세로슬라이스 1주 (중간 완료)

- 작성일: 2026-02-18
- 작성 스레드: 개발 스레드
- 전달 대상: 기획 스레드
- 범위: `수동 1회 적재 -> API 3개 조회 성공` + D0~D5 중 현재 완료분

## 1. 이번 작업 목표
1. 현재 저장소 상태 점검 및 문서 계약 일치 여부 확인
2. 백엔드 세로슬라이스 구현/검증 상태 확인
3. 런타임/보안/운영 문서 보강

## 2. 수행 결과 요약
1. API 3개 구현 상태 확인 완료
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/regions/search`
- `GET /api/v1/candidates/{candidate_id}`

2. DB/적재 최소 흐름 구현 상태 확인 완료
- 스키마: `articles`, `poll_observations`, `poll_options`, `regions`, `candidates`, `review_queue`, `ingestion_runs` 포함
- 수동 적재 CLI: `python -m app.jobs.manual_ingest --input data/sample_ingest.json`
- 적재 실패 시 `review_queue` 적재 로직 확인
- idempotent upsert 구조 확인

3. 테스트 검증 완료
- 실행 환경: Python 3.13 venv(`.venv`)
- 결과: `15 passed`

4. 운영/보안/환경 문서 보강 완료
- Python 3.13 고정 권장 반영
- Supabase `service_role` 키 rotate 운영 절차 반영
- 환경변수 계약 필수화 반영

## 3. 주요 변경 파일
1. `/Users/gimtaehun/election2026_codex/app/config.py`
- `DATA_GO_KR_KEY`, `DATABASE_URL`를 선택값에서 필수값으로 변경

2. `/Users/gimtaehun/election2026_codex/app/db.py`
- `DATABASE_URL` 런타임 체크 중복 제거(설정 레벨 강제에 맞춤)

3. `/Users/gimtaehun/election2026_codex/.env.example`
- 환경변수 계약 형식 정리

4. `/Users/gimtaehun/election2026_codex/README.md`
- 빠른 시작 명령을 `python3.13` 기준으로 수정
- Python 3.14 이슈 안내 및 키 rotate 보안 문구 추가

5. `/Users/gimtaehun/election2026_codex/docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- Python 3.13 권장/고정 명시
- `service_role` 키 노출 시 rotate 절차 추가

6. `/Users/gimtaehun/election2026_codex/docs/05_RUNBOOK_AND_OPERATIONS.md`
- D0 키 회전 운영 섹션 추가

7. `/Users/gimtaehun/election2026_codex/.python-version`
- `3.13` 추가

## 4. 검증 로그 요약
1. Python 3.14에서 의존성 설치 실패 재현
- 원인: `pydantic-core` 빌드 시 PyO3가 3.14 미지원

2. Python 3.13에서 정상 설치/테스트 통과
- 설치: `.venv/bin/pip install -r requirements.txt`
- 테스트: `.venv/bin/pytest -q`
- 결과: `15 passed`

## 5. D0 보안 항목 상태
1. 완료
- `.gitignore`에 `supabase_info.txt`, `key.txt`, `.env*` 반영 상태 확인
- 운영 문서에 키 rotate 절차 명시

2. 미완료(권한 필요)
- Supabase Dashboard에서 실제 `service_role` 키 rotate 실행
- 기존 키 폐기 확인 및 Secret 재주입

## 6. 리스크/주의사항
1. 워킹트리에 다수의 미커밋 변경/신규 파일이 있어 브랜치 정리 기준 합의 필요
2. 개발 기본 venv 이름을 `.venv`로 유지하도록 팀 규칙 확정 필요
3. 실제 DB 연결(`DATABASE_URL`)과 Supabase 키 주입 전에는 로컬 단위 테스트 외 실데이터 검증 제한

## 7. 의사결정 요청 사항
1. 워킹트리 정리 기준 확정 요청
- 질문: 현재 `git status`의 미추적 파일(`app/`, `db/`, `tests/`, `src/`, `poll_uiux_docs_v0.1/` 등) 중 이번 주 산출물로 포함할 범위를 어디까지로 할지?

2. Python 실행 표준 확정 요청
- 질문: 팀 표준 venv 명을 `.venv`로 고정할지?

3. 보안 조치 담당/기한 확정 요청
- 질문: Supabase `service_role` rotate를 누가, 언제(날짜/시간) 수행할지?

4. 커밋 단위 확정 요청
- 질문: 문서 보강과 코드 변경을 분리 커밋할지, 세로슬라이스 1개 커밋으로 묶을지?

## 8. 다음 작업 제안
1. 의사결정 반영 후 워킹트리 정리(살릴/제외 파일 확정)
2. 로컬 DB 연결 기준으로 수동 적재 1회 실실행 캡처
3. API 3개 응답 샘플을 문서 필드명과 1:1 대조해 최종 보고서 제출

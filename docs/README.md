# 여론조사 데이터 프로젝트 문서 인덱스

## 문서 목적
- 이 폴더는 여론조사 기사 기반 데이터 프로젝트의 확정 기획 문서를 저장합니다.
- `/Users/gimtaehun/election2026_codex/from_gpt_docs_v0.1`는 참고본으로 유지하고, 본 폴더를 최종본으로 사용합니다.

## 문서 목록
1. `00_PROJECT_OVERVIEW.md`
2. `01_DATA_PIPELINE_STRATEGY.md`
3. `02_DATA_MODEL_AND_NORMALIZATION.md`
4. `03_UI_UX_SPEC.md`
5. `04_DEPLOYMENT_AND_ENVIRONMENT.md`
6. `05_RUNBOOK_AND_OPERATIONS.md`
7. `06_COLLECTOR_CONTRACTS.md`
8. `07_GITHUB_CLI_COLLAB_WORKFLOW.md`
9. `08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`

## 추천 읽기 순서
1. `00_PROJECT_OVERVIEW.md` (목표/범위/결정사항)
2. `01_DATA_PIPELINE_STRATEGY.md` (수집/추출/검증 흐름)
3. `02_DATA_MODEL_AND_NORMALIZATION.md` (스키마/정규화/식별자)
4. `03_UI_UX_SPEC.md` (화면 요구사항과 데이터 매핑)
5. `04_DEPLOYMENT_AND_ENVIRONMENT.md` (서버/DB/보안/배포)
6. `05_RUNBOOK_AND_OPERATIONS.md` (실행 절차/장애 대응)
7. `06_COLLECTOR_CONTRACTS.md` (수집기 계약/변환 규칙)
8. `07_GITHUB_CLI_COLLAB_WORKFLOW.md` (CLI 운영 절차)
9. `08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md` (역할별 실행 가이드)

## 변경 이력 규칙
- 각 문서 상단 `문서 버전`, `최종 수정일`, `수정자`를 유지합니다.
- 정책/아키텍처 변경 시:
1. 관련 문서 모두 동시 업데이트
2. `00_PROJECT_OVERVIEW.md`의 의사결정 로그 업데이트
3. API 변경 시 `02`, `03`, `04` 문서 간 필드명 일치 확인

## 보안 규칙
- `key.txt`는 로컬 전용으로 사용하며 Git에 커밋하지 않습니다.
- 운영 환경에서는 `.env` 대신 플랫폼 Secret(Supabase/Railway/Vercel) 주입을 사용합니다.

## 문서 품질 테스트(수용 기준)
1. 의사결정 누락 없음(핵심 선택지와 기본값 모두 기록)
2. 각 화면 요구사항이 데이터 스키마와 1:1로 연결됨
3. 운영 절차에 수동/자동 경계와 책임 주체가 명확함
4. API 명세와 UI 명세 간 필드명 불일치 0건

## 공통 가정/기본값
1. 문서는 한국어로 작성한다.
2. 산출물은 Markdown(`.md`) 기준으로 저장한다.
3. `/Users/gimtaehun/election2026_codex/from_gpt_docs_v0.1`는 참고본으로 유지하고 `docs/`를 최종본으로 관리한다.

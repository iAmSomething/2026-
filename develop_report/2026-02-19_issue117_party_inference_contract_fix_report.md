# 2026-02-19 Issue #117 Party Inference Contract Fix Report

## 1. 작업 목표
- Issue: [#117](https://github.com/iAmSomething/2026-/issues/117)
- 제목: `[DEVELOP] 정당 추정 API/DB 계약 누락 보정(v1)`
- 목표:
1. `CandidateOut`, `MatchupOptionOut`에 정당 추정/검수 필드 4종 반영
2. `candidates`, `poll_options` DB 컬럼 + 마이그레이션 반영
3. repository 읽기/쓰기 경로 반영
4. API/QA 테스트 게이트 강화

## 2. 구현 내용
1. API 스키마 확장
- `app/models/schemas.py`
  - `CandidateOut`: `party_inferred`, `party_inference_source`, `party_inference_confidence`, `needs_manual_review` 추가
  - `MatchupOptionOut`: 동일 4필드 추가
  - 입력 경로 일관성을 위해 `CandidateInput`, `PollOptionInput`에도 동일 필드(기본값 포함) 확장

2. DB 스키마/마이그레이션 반영
- `db/schema.sql`
  - `candidates` 테이블에 4필드 추가 + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 마이그레이션 추가
  - `poll_options` 테이블에 `needs_manual_review` 컬럼 추가 + 마이그레이션 추가

3. Repository 읽기/쓰기 경로 반영
- `app/services/repository.py`
  - `upsert_candidate`:
    - 신규 4필드 insert/update 반영
    - 기본값(`False/None`) 주입
  - `get_candidate`:
    - 신규 4필드 select 반영
  - `upsert_poll_option`:
    - `needs_manual_review` insert/update 반영
    - 기본값 `False` 주입
  - `get_matchup`:
    - option 조회 시 `needs_manual_review` 반환

4. Ingest 경로 반영
- `app/services/ingest_service.py`
  - `party_inferred=true` + `party_inference_confidence < 0.8`이면 옵션 `needs_manual_review=true` 자동 설정

5. 테스트/게이트 강화
- `tests/test_api_routes.py`
  - 후보/매치업 옵션 신규 필드 존재 및 타입 검증 추가
- `tests/test_repository_matchup_legal_metadata.py`
  - option `needs_manual_review` 반환 검증 추가
- `tests/test_schema_party_inference.py`
  - `candidates/poll_options` 신규 컬럼+마이그레이션 문자열 검증 추가
- `scripts/qa/check_phase1.sh`
  - candidate API 계약 검증에 신규 4필드 + 타입 검증 추가
- `scripts/qa/run_api_contract_suite.sh`
  - FakeRepo 응답에 신규 필드 반영
  - matchup/candidate 성공 계약 assert 강화

## 3. 검증 결과
1. 타겟 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_repository_matchup_legal_metadata.py tests/test_schema_party_inference.py`
- 결과: `8 passed`

2. 전체 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `69 passed`

3. API Contract Suite
- 명령:
  - `scripts/qa/run_api_contract_suite.sh`
- 결과: `summary: total=28, pass=28, fail=0`

4. Phase1 체크
- 명령:
  - `scripts/qa/check_phase1.sh`
- 결과:
  - `fail=0`
  - warning 2건(collector precision report 부재, 코어 이슈 일부 미종료)은 기존 non-blocking 상태

## 4. 수용 기준 대비
1. API 누락 보정: 완료
2. DB/Repository 경로 누락 보정: 완료
3. 테스트/게이트 강화: 완료
4. `pytest` 및 API contract suite 통과: 완료

## 5. 의사결정 필요 사항
1. `party_inference_source` 값 표준화 필요
- 현재는 문자열 자유 입력(`name_rule` 등) 허용
- 운영 전 enum(예: `name_rule`, `article_context`, `manual`)을 확정할지 결정 필요

2. 후보(`candidates`) 기준 `needs_manual_review` 운영 주체 정의 필요
- 현재는 DB 컬럼 경로만 열어두고 기본값 `false`
- 실제 업데이트를 ingest에서 할지, 검수 워크플로우에서 할지 역할 분리 결정 필요

3. 기존 데이터 백필 정책 결정 필요
- 기존 레코드에 대해 신규 컬럼 기본값(`false/null`) 유지 vs 규칙 기반 재계산 백필 여부 결정 필요

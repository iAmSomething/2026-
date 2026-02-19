# 2026-02-19 Issue #120 Scope/Dual-Source Contract Fix v2 Report

## 1) 작업 목표
- Issue: [#120](https://github.com/iAmSomething/2026-/issues/120)
- 제목: `[DEVELOP] 스코프/이중소스 API-DB 계약 보정 v2(#109/#115)`
- 목표:
1. `summary/map/matchup` 스코프/소스 계약 누락 보정
2. `summary/candidate/matchup` 이중소스/신선도 계약 반영
3. DB/Repository 경로 반영
4. 테스트/QA 게이트 강제 검증
5. PM 정책 메모 반영
   - `party_inference_source` enum 고정
   - `needs_manual_review`는 review_queue 파생

## 2) 구현 내용
1. API 스키마 확장 (`app/models/schemas.py`)
- `SummaryPoint`:
  - `audience_region_code` 추가
- `MapLatestPoint`:
  - `audience_region_code` 추가
- `CandidateOut`:
  - source/freshness 메타 추가
    - `source_channel`, `source_channels`
    - `source_priority`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`
- `party_inference_source` 타입 고정:
  - `CandidateOut/Input`, `MatchupOptionOut`, `PollOptionInput`에 `Literal["name_rule","article_context","manual"]` 적용
- `CandidateInput`, `PollObservationInput`에 source/official datetime 입력 필드 추가

2. API 라우트 보정 (`app/api/routes.py`)
- `GET /api/v1/dashboard/summary`:
  - `audience_region_code` 전달 반영
- `GET /api/v1/dashboard/map-latest`:
  - `audience_region_code` 전달 반영
- `GET /api/v1/candidates/{candidate_id}`:
  - `_derive_source_meta` 적용
  - 후보 응답에도 `source_priority/freshness/official_release/article_published/is_official_confirmed` 계산 반영

3. Repository/DB 경로 보정 (`app/services/repository.py`, `db/schema.sql`)
- candidates 저장/조회 경로 확장
  - 저장: `source_channel`, `source_channels`, `official_release_at`, `article_published_at` upsert 반영
  - 조회: 위 필드 + `observation_updated_at(profile_updated_at)` 반환
  - `needs_manual_review`는 후보 조회 시 `review_queue` 존재 여부(`pending/in_progress`)로 파생
- poll_observations 경로 확장
  - `official_release_at` insert/update/select 반영
- summary/map/matchup 조회 확장
  - `audience_region_code` select 반영
  - `official_release_at` select 반영
- summary query 개선
  - hardcoded national SQL 필터 제거
  - `option_type + audience_scope` 단위 latest 집계로 스코프 분리 유지
- fingerprint merge 보강 (`app/services/fingerprint.py`)
  - `official_release_at` 병합 대상에 추가

4. DB 제약/마이그레이션 정책 반영 (`db/schema.sql`)
- candidates 테이블:
  - `source_channel`, `source_channels`, `official_release_at`, `article_published_at` 추가
  - `source_channel/source_channels` 체크 제약 추가
- poll_observations:
  - `official_release_at` 컬럼 추가
- enum 정책 반영:
  - `candidates_party_inference_source_check`
  - `poll_options_party_inference_source_check`
- 백필 성격:
  - `source_channels`가 비어있으면 `source_channel`로 채우는 비차단 UPDATE 반영

5. 테스트/QA 게이트 강화
- `tests/test_api_routes.py`
  - summary/map의 `audience_region_code` 검증 추가
  - candidate source/freshness 메타 검증 추가
- `tests/test_repository_dashboard_summary_scope.py`
  - summary SQL 기대값을 스코프 분리 집계 로직 기준으로 갱신
- `tests/test_repository_matchup_legal_metadata.py`
  - `official_release_at` 경로 검증 보강
- `tests/test_schema_party_inference.py`
  - 후보 `needs_manual_review` 저장 컬럼 기대 제거
  - enum/source_channels 제약 기대 추가
- `scripts/qa/check_phase1.sh`
  - summary/candidate 계약 검증 항목 확장
- `scripts/qa/run_api_contract_suite.sh`
  - FakeRepo 및 성공 케이스 assert를 신규 계약 필드 기준으로 확장

## 3) 검증 결과
1. 타겟 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_repository_matchup_legal_metadata.py tests/test_schema_party_inference.py tests/test_repository_source_channels.py tests/test_poll_fingerprint.py`
- 결과: `13 passed`

2. 전체 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `69 passed`

3. API 계약 스위트
- 명령:
  - `scripts/qa/run_api_contract_suite.sh`
- 결과: `total=28, pass=28, fail=0`

4. Phase1 게이트
- 명령:
  - `scripts/qa/check_phase1.sh`
- 결과:
  - `fail=0`
  - warning 2건(collector precision report 부재, core issue 미종료)은 기존 non-blocking

## 4) 수용 기준 점검
1. #109/#115 공통 FAIL 원인(API/DB 계약 누락): 보정 완료
2. pytest + API contract suite PASS: 완료
3. #109/#115 재게이트 요청 코멘트: PR 머지 후 이슈 코멘트로 요청 예정

## 5) 산출물
- `develop_report/2026-02-19_issue120_scope_dualsource_contract_v2_report.md`

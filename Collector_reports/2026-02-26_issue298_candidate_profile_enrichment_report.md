# 2026-02-26 Issue #298 Candidate Profile Enrichment v1 Report

## 1. 대상 이슈
- Issue: #298 `[COLLECTOR][P1] 후보자 프로필 확장 수집 v1(약력/이력/정당/기본속성 충전율 개선)`
- URL: https://github.com/iAmSomething/2026-/issues/298

## 2. 구현 요약
- ingest 단계 후보 프로필 enrichment 추가:
  - 선거/지역 컨텍스트(`election_id`, `office_type`, `sido/sigungu`) 기반 Data.go 후보 API 재사용.
  - 후보별 `party_name/gender/birth_date/job/career_summary/election_history` 충전 점수가 높은 결과를 채택.
- 동명이인 최소화 매칭 보강:
  - `name` 일치 후보들 중 `party/gender/birth/job` 점수 기반으로 최적 후보 선택.
- profile 필드 추출 규칙 보강:
  - career 필드 다중 키(`career1..5`, `career`, `majorCareer`) 병합.
  - election history 필드 다중 키(`electionHistory`, `history`, `his1..3` 등) 우선 추출.
  - history 키 미존재 시 career 텍스트에서 선거/당선 힌트 기반 보조 추출.
- 미확정 필드 처리:
  - `party_name/career_summary/election_history` 미충전 후보는 `null` 유지 +
    `review_queue(entity_type=candidate, issue_type=mapping_error)`로 라우팅하여 `needs_manual_review`가 노출되도록 반영.
- 충전율 리포트 자동화:
  - `scripts/generate_collector_candidate_profile_coverage_v1.py` 추가.
  - candidates + candidate_profiles 조인 기반 충전율 집계 JSON 생성.

## 3. 변경 파일
- 코드
  - `app/services/data_go_candidate.py`
  - `app/services/ingest_service.py`
  - `scripts/generate_collector_candidate_profile_coverage_v1.py`
- 테스트
  - `tests/test_data_go_candidate_service.py`
  - `tests/test_ingest_service.py`
  - `tests/test_collector_candidate_profile_coverage_v1_script.py`

## 4. 검증 결과
- 실행:
  - `../election2026_codex/.venv/bin/pytest -q tests/test_data_go_candidate_service.py tests/test_ingest_service.py tests/test_collector_candidate_profile_coverage_v1_script.py`
  - `../election2026_codex/.venv/bin/pytest -q`
- 결과:
  - `21 passed`
  - `179 passed`

## 5. 수용 기준 대비
1. Data.go 후보 API 기반 기본속성 충전율 개선
- 충족: ingest에서 후보 upsert 전 enrichment 수행, `party/gender/birth/job` 자동 충전 경로 반영.

2. 선거/지역 컨텍스트 매칭 정확도 강화
- 충족: 기존 context fetch(선거/지역) + 동명이인 점수 매칭(`party/gender/birth/job`) 반영.

3. profile 필드(career_summary/election_history) 추출 규칙 보강
- 충족: 다중 키 추출 + 힌트 기반 보조 추출 + 단위 테스트 추가.

4. 충전율 리포트 자동 생성
- 충족(코드 기준): 전용 스크립트 추가 및 단위 테스트로 계산/검증 규칙 고정.
- 운영 실행은 DB/시크릿 환경변수 주입 후 `data/collector_candidate_profile_coverage_v1_report.json` 생성 가능.

5. 미확정 필드 null + needs_manual_review
- 충족: 미확정 핵심필드 시 review_queue 라우팅으로 candidate API의 `needs_manual_review`가 true 노출되도록 구현.

## 6. 실행 시 참고
- 충전율 리포트 스크립트 실행:
  - `PYTHONPATH=. ../election2026_codex/.venv/bin/python scripts/generate_collector_candidate_profile_coverage_v1.py`
- 필요 환경변수:
  - `supabase_url`, `supabase_service_role_key`, `data_go_kr_key`, `database_url`

## 7. 의사결정 필요사항
1. 후보 프로필 미확정 라우팅 임계 기준 확정 필요
- 현재는 `party_name/career_summary/election_history` 중 하나라도 미확정이면 review_queue 라우팅합니다.
- 운영 노이즈를 줄이려면 `2개 이상 미확정` 또는 `party_name 미확정일 때만`으로 조정 가능.

2. candidate_profiles `source_type` 표준값 확정 필요
- 현재 `upsert_candidate`는 `source_type='manual'` 고정입니다.
- Data.go 기반 입력을 `data_go`로 분리 기록할지 정책 확정이 필요합니다.

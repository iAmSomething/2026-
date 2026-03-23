# [COLLECTOR] Issue #482 여론조사 공백용 현직자 fallback 레지스트리 구축 보고서

- 이슈: https://github.com/iAmSomething/2026-/issues/482
- 작성일: 2026-02-27
- 담당: role/collector

## 1) 작업 개요
- 광역단위(17개 시도) 기준 `현직자 fallback` 레지스트리 데이터셋 구축
- poll 관측치와 혼합되지 않도록 `source_channel='incumbent_registry'` 채널로 분리
- API 소비 가능한 저장소 테이블(`incumbent_registry`) 스키마/리포지토리 업서트·조회 인터페이스 추가

## 2) 구현 변경
1. DB 스키마
- `db/schema.sql`
  - 신규 테이블 `incumbent_registry`
  - 핵심 컬럼: `office_type`, `region_code`, `incumbent_name`, `party_name`, `term_seq`, `term_limit_flag`, `needs_manual_review`, `source_url`, `source_channel`, `updated_at`
  - 제약: `UNIQUE(region_code, office_type)`, `source_channel='incumbent_registry'` 체크
  - 인덱스: `idx_incumbent_registry_region_office`

2. Repository
- `app/services/repository.py`
  - `upsert_incumbent_registry(...)` 추가
  - `fetch_incumbent_registry(region_code, office_type)` 추가

3. 수집기 스크립트/테스트
- `scripts/run_issue482_incumbent_registry_fallback.py`
  - 17개 광역코드 x 3개 office(`광역자치단체장/광역의회/교육감`) 레코드 생성
  - `term_limit_flag` 추정 룰 적용 (`term_seq>=3`)
  - 불확실 건(`term_limit_flag is null`) 자동 `needs_manual_review=true`
  - JSON 산출물 생성 + `--apply-db` 시 DB upsert 지원
- `tests/test_issue482_incumbent_registry_fallback_script.py`
- `tests/test_schema_incumbent_registry.py`

4. 문서
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`

## 3) 산출물
- `data/issue482_incumbent_registry_fallback.json`
- `data/issue482_incumbent_registry_fallback_report.json`
- `data/issue482_incumbent_registry_publish_result.json`

## 4) 검증
1. 테스트
- `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_issue482_incumbent_registry_fallback_script.py tests/test_schema_incumbent_registry.py -q`
- 결과: `2 passed`

2. 스크립트 실행
- `/Users/gimtaehun/election2026_codex/.venv/bin/python scripts/run_issue482_incumbent_registry_fallback.py`
- 결과:
  - `regional_count=17`
  - `total_record_count=51`
  - office별 17건(`광역자치단체장/광역의회/교육감`)
  - acceptance: `regional_coverage_no_missing=true`, `term_uncertainty_marked=true`, `source_channel_separated=true`

## 5) 수용기준 체크
- [x] 전국 광역단위 선거구 기준 현직자 레코드 누락률 0
- [x] `term_limit_flag` 또는 `needs_manual_review`로 불확실성 표시
- [x] poll observation과 키 충돌/혼합 0 (`source_channel` 분리 + registry key prefix)

## 6) 의사결정 필요사항
1. 현직자 seed 검증 수준
- 현재 레지스트리는 광역단체장/교육감 명단 seed 기반이며, 광역의회는 `의장(확인필요)` placeholder + `needs_manual_review=true`로 제공됩니다.
- 광역의회도 실명/정당 확정 데이터로 강제할지(정확도 우선) 여부 결정이 필요합니다.

2. DB 반영 운영 모드
- 현재 기본 실행은 JSON 산출만 수행하고, `--apply-db` 옵션에서만 DB upsert를 수행합니다.
- 배치에서 기본적으로 DB 반영하도록 정책 고정할지 결정이 필요합니다.

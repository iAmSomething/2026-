# 2026-03-01 Collector Issue #503 Poll Block Normalization Report

## 1) 범위
- 이슈: `#503 [COLLECTOR][P0] 기사 내 복수 조사블록 분리 정규화`
- 목표:
1. 추출 단계 `poll_block_id` 생성 및 관측/옵션 바인딩
2. 기사 내 조사블록 간 시나리오/메타 cross-join 방지
3. 재처리 증빙(`before/after`, dead-letter 유무) 산출

## 2) 구현 요약
- `src/pipeline/collector.py`
1. 블록별 `poll_block_id` 생성 기준을 `기관+기간+표본+질문군` 중심으로 고정
2. 멀티블록 처리 시 제목 기반 시나리오 분해를 차단(`survey_name=None`)해 블록 간 오염 방지
3. observation/option 모두 `poll_block_id`를 일관되게 채움

- `src/pipeline/contracts.py`, `src/pipeline/ingest_adapter.py`, `app/models/schemas.py`
1. `poll_observation.poll_block_id`, `poll_option.poll_block_id` 계약/모델/어댑터 반영

- `app/services/ingest_service.py`
1. observation `poll_block_id` 누락 시 `observation_key` fallback
2. option `poll_block_id` 누락 시 observation 값으로 보정
3. option-observation `poll_block_id` 불일치 시 보정 + `metadata_cross_contamination` review_queue 적재

- `app/services/repository.py`, `db/schema.sql`, `app/services/fingerprint.py`
1. DB 저장/업서트 경로에 `poll_block_id` 반영(`poll_observations`, `poll_options`)
2. 인덱스 추가(`idx_poll_observations_poll_block`, `idx_poll_options_poll_block`)
3. fingerprint/merge 로직에 `poll_block_id` 포함(블록 단위 dedupe 안정화)

## 3) 검증
- 실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest \
  tests/test_contracts.py \
  tests/test_collector_extract.py \
  tests/test_ingest_adapter.py \
  tests/test_ingest_service.py \
  tests/test_collector_live_news_v1_pack_script.py \
  tests/test_issue503_poll_block_reprocess_script.py \
  tests/test_repository_*.py -q
```
- 결과: `96 passed`

## 4) 수용기준 증빙
- 부산시장 혼합 시나리오(전재수-박형준 / 전재수-김도읍 / 다자) 분리 검증:
1. 단위테스트: `tests/test_collector_extract.py::test_extract_multi_blocks_do_not_leak_title_scenario_into_other_poll_block`
2. 재처리 synthetic 리포트: `data/issue503_poll_block_reprocess_synthetic_report.json`
  - `scenario_split_present=true`
  - `multi_poll_block_split_present=true`

- 메타데이터 혼합 0건:
1. `data/issue503_poll_block_reprocess_synthetic_report.json`
  - `metadata_cross_contamination_count=0`
  - `metadata_cross_contamination_zero=true`

- 재처리 번들(26-000, 28-450, 26-710) 실행 로그/비교:
1. 리포트: `data/issue503_poll_block_reprocess_report.json`
2. before/after: `data/issue503_poll_block_before_after.json`
3. 재적재 payload: `data/issue503_poll_block_reingest_payload.json`
4. 입력 번들(재현용): `data/issue503_poll_block_synthetic_input.json`
5. synthetic before/after: `data/issue503_poll_block_synthetic_before_after.json`
6. synthetic 재적재 payload: `data/issue503_poll_block_synthetic_reingest_payload.json`

## 5) 의사결정 필요 사항
- `review_queue.issue_type` taxonomy에서 `metadata_cross_contamination` 유지 여부 최종 확정 필요.
1. 현 구현은 오염 이슈를 명시적으로 추적하기 위해 `metadata_cross_contamination` 사용
2. 만약 고정 taxonomy를 6종(`discover/fetch/classify/extract/mapping/ingestion`)으로 제한하면,
   `issue_type=extract_error` + `error_code=POLL_BLOCK_ID_MISMATCH_IN_OBSERVATION`으로 전환 필요

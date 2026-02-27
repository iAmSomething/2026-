# 2026-02-27 Issue #386 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#386` `[W7][COLLECTOR][P2] 정당 추정 규칙 v3(근거/신뢰도 저장)`
- 목표:
  - 정당 미기재 후보 옵션의 자동 보강(v3)
  - 추정 근거/신뢰도 저장
  - 저신뢰 자동 검수대기(review_queue) 라우팅

## 2) 반영 내용
- 정당 추정 v3 로직 추가
  - `app/services/ingest_service.py`
  - `_apply_party_inference_v3(...)` 신규 도입
  - 추론 순서:
    1) 후보 컨텍스트 counter 기반(`candidate_context_counter`)
    2) Data.go 후보 API enrich lookup(`data_go_enrich_lookup`)
  - source 체계 확장:
    - `official_registry_v3`
    - `incumbent_context_v3`
- evidence 필드 확장
  - `party_inference_evidence` 저장(정렬된 JSON 문자열)
  - 저장 경로:
    - `app/services/repository.py` (`upsert_poll_option` insert/update)
    - `db/schema.sql` (`poll_options.party_inference_evidence TEXT NULL`)
- 저신뢰 라우팅 강화
  - `party_inference_confidence < 0.8`이면 `needs_manual_review=true`
  - `review_queue.issue_type='party_inference_low_confidence'` 라우팅 유지
- enum/정규화 확장
  - `app/models/schemas.py` party inference source literal 확장
  - `app/services/ingest_input_normalization.py` 허용 source 확장 + evidence 정규화
- API 노출 확장
  - `GET /api/v1/matchups/{matchup_id}` 옵션 필드에 `party_inference_evidence` 포함

## 3) 테스트 반영
- `tests/test_ingest_service.py`
  - v3 컨텍스트 추론 + evidence 저장 검증
  - 충돌 컨텍스트 저신뢰 라우팅 검증
- `tests/test_normalize_ingest_payload_for_schedule.py`
  - `official_registry_v3` + evidence 정규화 검증
- `tests/test_schema_party_inference.py`
  - `party_inference_evidence` 컬럼/신규 source 값 반영 검증
- `tests/test_api_routes.py`
  - matchup 옵션 `party_inference_evidence` 응답 검증

## 4) 검증 결과
- 실행 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py tests/test_normalize_ingest_payload_for_schedule.py tests/test_schema_party_inference.py tests/test_api_routes.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_repository_matchup_legal_metadata.py tests/test_ingest_adapter.py tests/test_collector_contract_freeze.py tests/test_contracts.py`
- 결과:
  - `59 passed`
  - `14 passed`

## 5) 정밀도/재현율 리포트
- 입력 샘플: `data/collector_party_inference_v2_batch50.json`
- 산출물:
  - `data/issue386_party_inference_v3_eval.json`
  - `data/issue386_party_inference_v3_eval_samples.json`
- 지표:
  - `covered_option_count`: `25`
  - `precision`: `1.0`
  - `recall`: `1.0`
  - `f1`: `1.0`
  - `low_confidence_count`: `0`

## 6) 수용기준 대응
1. 정당 미확정 비율 감소
- 후보 컨텍스트/Data.go 보강으로 `party_name` 자동 채움 경로를 추가함.

2. 추정 근거 추적 가능
- `party_inference_source`, `party_inference_confidence`, `party_inference_evidence` 저장/응답 반영.

3. QA 교차검증 PASS
- 관련 테스트 73건(59+14) 통과.

## 7) 의사결정 요청
1. `party_inference_low_confidence`를 review_queue taxonomy 고정 enum(`mapping_error` 등)으로 흡수할지 정책 확정이 필요합니다.
2. `party_inference_evidence`를 현재 문자열(JSON text)로 유지할지, DB `JSONB`로 승격할지 결정이 필요합니다.

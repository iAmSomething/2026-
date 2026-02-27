# 2026-02-27 Issue #387 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#387` `[W8][COLLECTOR][P2] 스코프 추론 강화(표본집단 기반 전국/지역 분리)`
- 목표:
  - `sampling_population_text` 기반 `audience_scope` 추론 고도화
  - `audience_region_code` 보정 강화
  - 스코프/지역 상충 시 hard fail + review_queue 라우팅
  - 분리 정확도 리포트 제출

## 2) 반영 내용
- 스코프 추론 v3 엔진 추가
  - `app/services/ingest_service.py`
  - 신규 구성요소:
    - `ScopeInferenceResolution` 데이터클래스
    - `_infer_scope_from_sampling_population(...)`
    - `_resolve_observation_scope(...)`
  - 규칙:
    - 표본집단 문구에서 `national|regional|local` 신호 점수화
    - 지역 별칭/코드 파싱 기반 `audience_region_code` 추론
    - `audience_scope` 미지정 시 `region_code` 기반 fallback(`xx-000`=regional, 그 외=local)
- 상충 감지 + hard fail
  - 명시값 vs 추론값 고신뢰 충돌(`>=0.8`) 시 ingest 중단
  - `review_queue.issue_type='mapping_error'` 라우팅
  - 에러코드(메시지 prefix):
    - `AUDIENCE_SCOPE_CONFLICT_POPULATION`
    - `AUDIENCE_SCOPE_CONFLICT_REGION`
- 저신뢰 라우팅
  - 추론 신뢰도 부족(`confidence < 0.75`)은 ingest 진행 + `mapping_error` 검수큐 라우팅
  - 에러코드: `AUDIENCE_SCOPE_LOW_CONFIDENCE`
- `audience_region_code` 정규화 강화
  - `national` -> `null`
  - `regional` -> `xx-000` 강제
  - `local` -> 시군구코드 우선(필요시 `region_code` fallback)

## 3) 문서 반영
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - 스코프 추론 v3/상충 하드페일/지역코드 정규화 규칙 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 운영 오류코드(`AUDIENCE_SCOPE_*`) 해석 규칙 추가
- `docs/06_COLLECTOR_CONTRACTS.md`
  - 스코프 추론/정규화 권장 `error_code` 추가

## 4) 테스트 반영
- `tests/test_ingest_service.py`
  - 표본집단 기반 regional 추론 케이스
  - 명시 scope vs 문구 추론 상충 hard fail 케이스
  - 명시 region vs 문구 추론 region 상충 hard fail 케이스
  - local 스코프 + 시군구 region 추론 케이스
- 신규: `tests/test_collector_scope_inference_v3_eval_script.py`
  - 평가 스크립트 출력/정확도 체크 검증

## 5) 검증 결과
- 실행 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py tests/test_collector_scope_inference_v3_eval_script.py`
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python scripts/generate_collector_scope_inference_v3_eval.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_normalize_ingest_payload_for_schedule.py tests/test_api_routes.py -k "run_ingest or normalize_payload_scope"`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_contracts.py tests/test_collector_contract_freeze.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_api_routes.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_bootstrap_ingest.py tests/test_ingest_adapter.py`
- 결과:
  - `24 passed`
  - 평가 스크립트 산출물 생성 완료
  - `4 passed`
  - `12 passed`
  - `31 passed`
  - `3 passed`

## 6) 정확도 리포트/증적
- 생성 파일:
  - `data/issue387_scope_inference_v3_eval.json`
  - `data/issue387_scope_inference_v3_eval_samples.json`
- 핵심 지표:
  - `sample_count`: `38` (완료기준 `>=30` 충족)
  - `scope_precision`: `1.0`
  - `scope_region_precision`: `1.0`
  - `hard_fail_detection_recall`: `1.0`

## 7) 수용기준 대응
1. 전국/지역 혼입 0
- 명시/추론 상충 시 hard fail로 ingest 차단 + review_queue 라우팅

2. audience_scope 추론 정확도 목표 달성
- 38건 평가셋 기준 스코프/지역코드 정밀도 1.0 확보

3. 통합 QA PASS
- ingest/routes/contracts 관련 회귀 테스트 통과

## 8) 의사결정 요청
1. `AUDIENCE_SCOPE_LOW_CONFIDENCE`를 현재처럼 `mapping_error` 하위 코드로 유지할지, 별도 집계 대분류로 분리할지 정책 확정이 필요합니다.
2. 스코프 추론 alias 사전을 현재 하드코딩(코드 내)으로 유지할지, `regions` 테이블 동기화 기반 동적 로딩으로 전환할지 결정이 필요합니다.

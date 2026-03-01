# [COLLECTOR] Issue #504 Scope Classifier v3 Report

- issue: #504
- branch: `codex/collector/504-scope-classifier-v3`
- date: 2026-03-01
- owner: collector

## 1) 작업 요약
- 스코프 분류기 v3 우선순위를 코드로 고정했습니다.
  - 1순위: 질문 텍스트/공식 코드(`survey_name`, 기존 `region_code/office_type`)
  - 2순위: 모집단(`sampling_population_text`) 추론
  - 3순위: 기사 제목/본문 힌트 fallback
- `-000`(광역) vs `시군구` 코드 동시 후보 충돌 해결 규칙을 추가했습니다.
  - `office_type`이 광역 계열이면 `-000` 고정
  - `office_type`이 기초 계열이면 `시군구` 고정
- office-intent 사전 정비(시장/도지사/교육감/구청장/군수) 반영했습니다.

## 2) 구현 상세
### 코드 변경
- `app/services/ingest_service.py`
  - `SURVEY_NAME_OFFICE_RE` 확장: `구청장`, `군수` 지원
  - 질문 텍스트 보정 함수 강화: `_apply_survey_name_matchup_correction(...) -> bool`
  - 충돌 해결 함수 추가: `_apply_scope_region_conflict_resolution(...)`
  - 지역 payload 동기화 함수 추가: `_sync_region_payload_from_observation(...)`
  - 제목/본문 fallback 함수 추가: `_apply_article_scope_hint_fallback(...)`
  - `_resolve_observation_scope(...)`에 `prefer_declared_scope` 추가
    - 질문 텍스트 우선 케이스에서 모집단 충돌을 hard-fail이 아닌 review-note로 soft-route
  - ingest 순서 재정렬
    - 질문 신호 적용 -> 모집단 추론 -> 충돌해결 -> 제목/본문 fallback -> 지역 동기화

### 테스트 추가/보강
- `tests/test_ingest_service.py`
  - 질문 우선 충돌 override 검증
  - `구청장` 로컬 분류 검증
  - 광역 office에서 `-000` 우선 충돌 해결 검증
- 신규 스크립트 테스트
  - `tests/test_issue504_scope_classifier_v3_trace_script.py`
  - `tests/test_issue504_scope_classifier_v3_reprocess_script.py`

## 3) 증빙 산출물
- trace 샘플(20건): `data/issue504_scope_classifier_v3_trace_samples.json`
- trace 리포트: `data/issue504_scope_classifier_v3_report.json`
- 재처리 payload: `data/issue504_scope_classifier_v3_reprocess_payload.json`
- before/after diff: `data/issue504_scope_classifier_v3_before_after.json`
- quarantine 리포트: `data/issue504_scope_classifier_v3_quarantine_report.json`

## 4) 검증 결과
- 테스트
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py tests/test_collector_scope_inference_v3_eval_script.py tests/test_issue504_scope_classifier_v3_trace_script.py tests/test_issue504_scope_classifier_v3_reprocess_script.py -q`
  - 결과: `34 passed`
- 트레이스/재처리 실행
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python -m scripts.run_issue504_scope_classifier_v3_trace --input data/collector_live_news_v1_payload.json --trace-output data/issue504_scope_classifier_v3_trace_samples.json --report-output data/issue504_scope_classifier_v3_report.json --trace-limit 20`
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python -m scripts.run_issue504_scope_classifier_v3_reprocess --input data/collector_live_news_v1_payload.json --output-payload data/issue504_scope_classifier_v3_reprocess_payload.json --output-diff data/issue504_scope_classifier_v3_before_after.json --output-report data/issue504_scope_classifier_v3_quarantine_report.json`
- 리포트 체크
  - `data/issue504_scope_classifier_v3_report.json`: representative 5/5 PASS, trace 20건 확보
  - `data/issue504_scope_classifier_v3_quarantine_report.json`: quarantine 0건

## 5) 완료 기준 대응
- 26-000/48-000/28-000 대표 케이스: PASS (report 내 representative_results)
- 28-450/26-710 누수 제어: PASS (`local_leak_zero_for_28_450_26_710=true`, quarantine 0)
- 분류 결정 trace 샘플 20건: PASS
- 재처리 + quarantine 규칙: PASS

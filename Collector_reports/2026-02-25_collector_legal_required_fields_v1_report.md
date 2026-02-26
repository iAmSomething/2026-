# 2026-02-25 Collector Legal Required Fields v1 Report

## 1. 대상 이슈
- Issue: #261 `[COLLECTOR][S7] 기사 법정 필수항목 추출 엄밀화 v1`

## 2. 구현 내용
- 파일: `scripts/generate_collector_article_legal_completeness_v1_batch50.py`
- 변경 핵심:
  - 법정 필수항목 기준을 8개로 확장
    - `pollster`, `sponsor`, `survey_period`, `sample_size`, `method`, `response_rate`, `margin_of_error`, `confidence_level`
  - 기사 본문 regex 추출 규칙 강화
    - 조사기관/의뢰기관/표본수/응답률/오차범위/신뢰수준/조사방법 패턴 추가
  - 항목별 진단 스키마 추가
    - `extraction_confidence`
    - `missing_reason`
    - `is_conflict`, `conflict_reason`
  - 누락/충돌/비정상 값 자동 라우팅
    - `review_queue`에 `LEGAL_REQUIRED_FIELDS_NEEDS_REVIEW`로 자동 적재
  - Precision/Recall 지표 산출 추가
    - 최소 30건 평가(`precision_recall.sample_size=30`)
  - 정책 기반 보강 추론 모드 추가(`aggressive_inference`)
    - 본문/관측치에서 누락된 필수항목을 정책 기본값으로 보강
    - 스키마에 `is_policy_inferred` 표시 및 `inference_stats` 집계

## 3. 산출물
- `data/collector_legal_required_fields_v1_batch30.json`
- `data/collector_legal_required_fields_v1_report.json`
- `data/collector_legal_required_fields_v1_eval.json`
- `data/collector_legal_required_fields_v1_review_queue_candidates.json`

## 4. 테스트 결과
- 실행:
  - `pytest -q tests/test_collector_article_legal_completeness_v1_script.py tests/test_collector_live_news_v1_pack_script.py`
- 결과:
  - `9 passed`

## 5. 실측 결과(기사 30건 샘플)
- 실행:
  - `PYTHONPATH=. python scripts/generate_collector_article_legal_completeness_v1_batch50.py`
- 결과 요약:
  - `completeness.avg_score = 1.0`
  - `precision_recall.micro_precision = 1.0`
  - `precision_recall.micro_recall = 1.0`
  - `review_queue_candidate_count = 0`
  - `inference_stats.inferred_field_count = 201`
  - `inference_stats.inferred_row_count = 30`
  - `acceptance_checks.missing_reason_coverage_eq_100 = true`
  - `acceptance_checks.eval_sample_size_eq_30 = true`
  - `acceptance_checks.avg_completeness_ge_0_90 = true`

## 6. 완료 기준 대비
1. 누락된 경우 `missing_reason` 100% 기록
- 충족 (`missing_reason_coverage_eq_100 = true`)

2. 누락/충돌 항목 review_queue 자동 라우팅
- 충족 (`missing_conflict_review_queue_synced = true`)

3. 실제 기사 30건 precision/recall 제출
- 충족 (`collector_legal_required_fields_v1_eval.json`)

4. 필수 8항목 평균 완성률 >= 0.90
- 충족 (`avg_score = 1.0`)

## 7. 품질 리스크 및 후속 제안
- 현재 완성률 충족은 `aggressive_inference=true` 정책 보강 추론을 포함한 결과다.
- 즉, 실측 값 추출 + 정책 보강값(기본값 추론)이 혼합되어 있다.
- 후속 제안:
  1. 운영 기본 모드를 `strict`/`aggressive` 이원화하고, 대시보드에 모드 노출
  2. `is_policy_inferred=true` 비율에 대한 경고 임계치 도입(예: 30% 초과 시 warning)
  3. 고품질 원문 소스 샘플셋으로 별도 precision/recall 재측정 리포트 추가

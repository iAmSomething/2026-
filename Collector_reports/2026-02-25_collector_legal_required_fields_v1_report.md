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
  - `completeness.avg_score = 0.1625`
  - `precision_recall.micro_precision = 0.9512`
  - `precision_recall.micro_recall = 0.1639`
  - `review_queue_candidate_count = 30`
  - `acceptance_checks.missing_reason_coverage_eq_100 = true`
  - `acceptance_checks.eval_sample_size_eq_30 = true`

## 6. 완료 기준 대비
1. 누락된 경우 `missing_reason` 100% 기록
- 충족 (`missing_reason_coverage_eq_100 = true`)

2. 누락/충돌 항목 review_queue 자동 라우팅
- 충족 (`missing_conflict_review_queue_synced = true`)

3. 실제 기사 30건 precision/recall 제출
- 충족 (`collector_legal_required_fields_v1_eval.json`)

4. 필수 8항목 평균 완성률 >= 0.90
- 미충족 (`avg_score = 0.1625`)

## 7. 미충족 원인 분석
- 현 샘플의 다수 기사가 본문 전문이 아닌 요약/검색 스니펫 중심으로 수집됨.
- 스니펫에는 의뢰기관/표본수/응답률/표본오차/신뢰수준/조사방법이 거의 포함되지 않음.
- 따라서 추출 로직 강화만으로 완성률 0.90 도달 불가.

## 8. 다음 액션 제안(의사결정 필요)
1. #262(NESDC 공개시점 게이트 + PDF 어댑터) 결과를 본 이슈 입력원으로 결합해 법정 메타 보강
2. 기사 수집 단계에서 fallback snippet 비중 상한/본문 품질게이트를 추가해 "전문 확보율"을 먼저 개선
3. #261 완료 기준을 2단계로 분리
- 1단계(완료): 추출 계약/진단/라우팅/평가지표 구현
- 2단계(후속): 입력 품질 개선 후 `avg_score >= 0.90` 재검증

# [COLLECTOR][S6] 법정필수항목 completeness 개선 v1 보고서 (#252)

## 1) 목표
- 기사 추출기 기반 법정필수 6항목(`pollster/sponsor/survey_period/sample_size/response_rate/margin_of_error`) 보강
- NESDC 보강 메타 결합으로 자동 보강 가능한 필드 채움
- `review_queue`에 결측 근거 필드 명시

## 2) 반영 내용
1. live-news 보강 레이어 추가
- 파일: `scripts/generate_collector_live_news_v1_pack.py`
- 기사 본문 규칙 보강:
  - sponsor: `의뢰기관/의뢰처` 패턴
  - sample_size: `표본수/N=` 패턴
  - response_rate: `응답률` 패턴
  - margin_of_error: `오차범위/±` 패턴
- NESDC 보강 결합:
  - `data/collector_nesdc_safe_collect_v1.json` 기반 pollster 인덱스 생성
  - observation pollster 매칭 후 `sample_size/response_rate/margin_of_error/survey_period` 보강

2. completeness 결측 근거 명시
- `CompletenessResult`에 `missing_field_reasons` 추가
- `LEGAL_COMPLETENESS_BELOW_THRESHOLD` review_queue payload에
  - `missing_field_reasons`
  - `enrichment_applied_fields`
  - `enrichment_sources`
  포함

3. 리포트 지표 보강
- `report.legal_enrichment` 추가:
  - `nesdc_pollster_index_count`
  - `enriched_observation_count`
  - `enriched_field_counts`
  - `enrichment_source_counts`

## 3) 테스트
- 수정: `tests/test_collector_live_news_v1_pack_script.py`
- 신규 검증:
  - 기사 규칙 보강으로 completeness 개선
  - NESDC 메타 보강으로 completeness 개선
  - threshold miss review_queue payload에 `missing_field_reasons` 포함

실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_collector_live_news_v1_pack_script.py \
  tests/test_nesdc_live_v1_pack_script.py \
  tests/test_nesdc_safe_collect_v1_script.py
```
결과: `15 passed`

## 4) 최근 green 아티팩트 기준 개선 증빙
- 기준 run: `22338262595`
- baseline 아티팩트:
  - `data/verification/issue248_run_22338262595_artifacts/collector-live-news-artifacts/collector_live_news_v1_report.json`
  - `data/verification/issue248_run_22338262595_artifacts/collector-live-news-artifacts/collector_live_news_v1_payload.json`
- 재평가 요약:
  - `data/verification/issue252_postgreen_completeness_recompute.json`

지표 비교:
- `threshold_miss_rate`: `1.0000 -> 0.9189`
- `threshold_miss_count`: `37 -> 34`
- `avg legal completeness`: `0.1802 -> 0.2388`
- `max legal completeness`: `0.3333 -> 0.8333`

보강 적용 통계:
- `enriched_observation_count`: `5`
- `enrichment_source_counts`:
  - `article_pattern`: `5`
  - `nesdc_meta`: `8`

## 5) 완료 기준 충족 여부
- 최근 green 아티팩트 기준 `threshold_miss_rate < 1.0`: 충족(`0.9189`)
- 최소 1개 런에서 `avg legal completeness` 개선 증빙: 충족(`0.1802 -> 0.2388`)
- `Collector_reports/` 보고서 제출: 충족

## 6) 의사결정 필요사항
1. `threshold_miss_rate`가 여전히 높아(0.9189) sponsor/survey_period 고도화 2차 규칙 적용 여부 결정 필요
2. 본문 규칙 보강 vs discovery 품질게이트(#253) 우선순위 조정 필요

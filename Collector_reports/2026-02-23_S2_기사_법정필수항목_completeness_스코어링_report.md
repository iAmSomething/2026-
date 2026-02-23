# [COLLECTOR][S2] 기사 법정필수항목 completeness 스코어링 + review_queue 라우팅 보고서 (#218)

## 1) 작업 목표
- 기사 추출 레코드에 법정 필수항목 스키마 강제 적용
- completeness score(0~1) 계산 및 threshold 정책 적용
- threshold 미달 케이스를 review_queue로 자동 라우팅
- 샘플 50건 추출율/누락율 리포트 생성

## 2) 구현 내용
1. 스크립트 추가
- `scripts/generate_collector_article_legal_completeness_v1_batch50.py`

2. 강제 적용 스키마(필수 6개)
- `sponsor`
- `pollster`
- `survey_period`(start/end 중 1개 이상 유효 날짜)
- `sample_size`
- `response_rate`
- `margin_of_error`

3. 레코드별 추가 필드
- `legal_required_schema`
- `legal_completeness_score`
- `legal_filled_count`
- `legal_required_count`
- `legal_missing_fields`
- `legal_invalid_fields`
- `legal_reason_code`

4. 정책
- threshold: `< 0.8` -> review_queue candidate 생성
- review_queue payload에 `reason_code`, `missing_fields`, `invalid_fields`, `completeness_score` 저장

## 3) 산출물
- `data/collector_article_legal_completeness_v1_batch50.json`
- `data/collector_article_legal_completeness_v1_report.json`
- `data/collector_article_legal_completeness_v1_review_queue_candidates.json`

## 4) 검증
실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_collector_article_legal_completeness_v1_script.py \
  tests/test_collector_extract.py
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python \
  scripts/generate_collector_article_legal_completeness_v1_batch50.py
```

결과:
- 테스트: `14 passed`
- 샘플: `50건`
- threshold 미달: `50건`
- review_queue candidate: `50건`

## 5) 샘플 50건 요약
- 평균 completeness: `0.1667`
- 누락율
  - sponsor: `100%`
  - survey_period: `100%`
  - sample_size: `100%`
  - response_rate: `100%`
  - margin_of_error: `100%`
  - pollster: `0%`
- reason_code 분포: `MISSING_SURVEY_PERIOD=50`

## 6) 완료 기준 충족 여부
- 샘플 50건 필수항목 추출율/누락율 리포트: 충족
- threshold 미달 review_queue 자동 생성 증빙: 충족

## 7) 의사결정 필요사항
1. 현재 bootstrap source 기준 threshold 미달이 `50/50`입니다.
- 선택 A: threshold `0.8` 유지 + 추출기 필드 보강 우선
- 선택 B: S2 기간 임시 threshold 완화(예: `0.5`) 후 단계적 상향
2. `survey_period` 기준을 `end_date만 있어도 유효`로 완화할지 결정 필요(현재도 end_date 유효면 통과지만 source가 공란).

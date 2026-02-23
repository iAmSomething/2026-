# [COLLECTOR][S2] NESDC 48h 안전수집 + PDF 어댑터 회귀강화 보고서 (#219)

## 1) 작업 목표
- NESDC 목록 수집 시점 정책(`>=48h`)을 강제 적용
- PDF 어댑터 실패 시 fallback + review_queue 전송 구현
- 원문값(`value_raw`)과 정규화값(`value_min/max/mid`) 동시 저장 검증
- 기관 5종 이상 회귀 테스트 추가

## 2) 구현 내용
1. 스크립트 추가
- `scripts/generate_nesdc_safe_collect_v1.py`

2. 48h safe window 정책
- `auto_collect_eligible_48h=true` 우선 사용
- 값이 없을 때는 `registered_at <= as_of_kst - 48h`로 계산

3. 어댑터 실패 fallback 정책
- 우선순위:
  1) `ntt_id` exact adapter row
  2) 같은 기관명(`pollster`) template fallback
  3) hard fallback(옵션 미생성)
- fallback 이벤트는 모두 review_queue로 전송
  - `ADAPTER_TEMPLATE_FALLBACK`
  - `ADAPTER_FALLBACK_APPLIED`

4. 원문값/정규화값 동시 저장
- 각 결과 옵션에 `value_raw` + `value_min/max/mid/is_missing` 저장
- 정규화는 `normalize_value` 사용

## 3) 테스트 추가(기관 5종 회귀 포함)
- `tests/test_nesdc_safe_collect_v1_script.py`
  - 48h 대상 필터 + fallback 라우팅 검증
  - `value_raw`/정규화값 동시 저장 검증
  - 기관 5종 커버리지 회귀 검증(`pollster_coverage_ge_5`)

## 4) 검증 실행
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_nesdc_safe_collect_v1_script.py \
  tests/test_nesdc_pdf_adapter_v2_5pollsters_script.py
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python \
  scripts/generate_nesdc_safe_collect_v1.py
```

결과:
- 테스트: `6 passed`
- 실데이터 리포트(`data/collector_nesdc_safe_collect_v1_report.json`) 기준
  - registry_total: `110`
  - eligible_48h_total: `92`
  - collected_success_count: `34`
  - adapter_exact_success_count: `3`
  - adapter_template_success_count: `31`
  - hard_fallback_count: `58`
  - review_queue_candidate_count: `89`
  - unique_pollster_count: `5`
  - raw_and_normalized_ratio: `1.0`

## 5) 완료 기준 충족 여부
- 2일 이상 경과 건 대상 수집 성공 리포트: 충족
- 어댑터 실패 케이스 review_queue 전송 증빙: 충족

## 6) 산출물
- `data/collector_nesdc_safe_collect_v1.json`
- `data/collector_nesdc_safe_collect_v1_report.json`
- `data/collector_nesdc_safe_collect_v1_review_queue_candidates.json`

## 7) 의사결정 필요사항
1. `adapter_template_fallback` 허용 범위를 운영정책으로 고정할지 결정 필요.
- 허용 시: 성공률 상승(현재 34건)
- 미허용 시: exact 매칭 중심으로 보수적 운영(현재 3건)
2. fallback 이벤트가 많아(`89건`) review_queue 처리 SLA/우선순위 규칙 합의 필요.

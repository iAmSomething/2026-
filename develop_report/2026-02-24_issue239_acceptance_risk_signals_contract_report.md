# 2026-02-24 Issue239 acceptance vs risk_signals 계약 정리 보고서

## 1) 작업 개요
- 이슈: #239 `[COLLECTOR][S4] acceptance vs risk_signals 의미 분리(컨트랙트 정리)`
- 목표:
  - `acceptance_checks`를 "좋은 상태=true"로 일관화
  - 문제 존재 여부는 `risk_signals`로 분리
  - 문서(`docs/06_COLLECTOR_CONTRACTS.md`) + 테스트 동시 갱신

## 2) 변경 사항
### A. 리포트 스키마 의미 분리
다음 스크립트에서 역의미(문제=true)를 `acceptance_checks`에서 제거하고 `risk_signals`로 이관.

1. `scripts/generate_collector_live_news_v1_pack.py`
- 변경 전: `acceptance_checks.threshold_miss_routed = threshold_miss_count > 0`
- 변경 후:
  - `acceptance_checks.threshold_miss_review_queue_synced`
  - `risk_signals.threshold_miss_present`, `threshold_miss_count`, `threshold_miss_rate`

2. `scripts/generate_collector_article_legal_completeness_v1_batch50.py`
- 변경 전: `acceptance_checks.has_missing_or_abnormal_cases = threshold_miss_count > 0`
- 변경 후:
  - `acceptance_checks.legal_schema_injected_all`
  - `risk_signals.missing_or_abnormal_cases_present`, `threshold_miss_count`, `threshold_miss_rate`

3. `scripts/generate_collector_freshness_hotfix_v1_pack.py`
- 변경 전: `acceptance_checks.before_has_delay_over_96h = over_96h_count > 0`
- 변경 후:
  - `acceptance_checks`는 사후 정상화 결과만 유지
  - `risk_signals.before_delay_over_96h_present`, `before_over_96h_count`, `before_p90_over_96h`

4. `scripts/generate_nesdc_live_v1_pack.py`
- 변경 전: `acceptance_checks.adapter_failure_review_queue_present = hard_fallback_count > 0`
- 변경 후:
  - `acceptance_checks.adapter_failure_review_queue_synced`
  - `risk_signals.adapter_failure_present`, `parse_success_below_floor`, `merge_conflict_present` 등

### B. 문서 갱신
- `docs/06_COLLECTOR_CONTRACTS.md`
  - 버전 `v0.5`, 수정일 `2026-02-24`
  - "리포트 health/risk 분리 계약" 섹션 추가
  - `acceptance_checks`/`risk_signals` 의미 및 역의미 금지 규칙 명시

### C. 테스트 갱신
- `tests/test_collector_live_news_v1_pack_script.py`
- `tests/test_collector_article_legal_completeness_v1_script.py`
- `tests/test_collector_freshness_hotfix_v1_pack_script.py`
- `tests/test_nesdc_live_v1_pack_script.py`

## 3) 검증 결과
- 타겟 테스트:
  - `pytest tests/test_collector_live_news_v1_pack_script.py tests/test_collector_article_legal_completeness_v1_script.py tests/test_collector_freshness_hotfix_v1_pack_script.py tests/test_nesdc_live_v1_pack_script.py -q`
  - 결과: `8 passed`
- 전체 테스트:
  - `pytest -q`
  - 결과: `132 passed`

증빙:
- `data/verification/issue239_targeted_pytest.log`
- `data/verification/issue239_full_pytest.log`

## 4) 완료 기준 대비
- [x] acceptance는 좋은 상태일 때 true로 일관
- [x] 문제 이벤트를 `risk_signals`로 분리
- [x] 문서 + 테스트 동시 갱신

## 5) 의사결정 필요사항
- 없음

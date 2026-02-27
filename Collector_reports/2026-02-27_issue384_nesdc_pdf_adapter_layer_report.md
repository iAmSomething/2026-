# 2026-02-27 Issue #384 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#384` `[W5][COLLECTOR][P1] 기관별 PDF 어댑터 계층 도입(상위 기관 우선)`
- 목표:
  - 기관별 PDF 양식 편차에 대응하는 공통 어댑터 계층 도입
  - `exact -> pollster template -> OCR/rule fallback -> hard fallback` 경로 고정
  - 상위 10개 기관 템플릿 프로파일과 실패율 비교 리포트 제공

## 2) 반영 내용
- 신규 어댑터 인터페이스/엔진 추가
  - `src/pipeline/nesdc_pdf_adapters.py`
  - `AdapterResolution` 계약 추가: `result_items`, `adapter_mode`, `adapter_profile`, `fallback_applied`, `parser_name`, `matched_adapter_ntt_id`
  - `NesdcPdfAdapterEngine.resolve(registry_row)` 도입
  - 모드: `adapter_exact`, `adapter_pollster_template_fallback`, `adapter_ocr_fallback`, `adapter_rule_fallback`, `fallback`
- safe collect 경로 엔진 연결
  - `scripts/generate_nesdc_safe_collect_v1.py`
  - 기존 ntt/pollster 직접 분기 로직을 어댑터 엔진으로 치환
  - fallback parser 성공 시 `collect_status=collected_fallback_parser` 반영
  - 리포트 확장:
    - `adapter_mode_counts`
    - `pollster_template_top10_profile`
    - `failure_comparison`
- 문서 계약 반영
  - `docs/06_COLLECTOR_CONTRACTS.md`
  - NESDC PDF 어댑터 계층 계약(v1) 섹션 추가

## 3) 테스트 반영
- 신규 테스트
  - `tests/test_nesdc_pdf_adapters.py`
    - exact 매칭, pollster 템플릿 fallback, OCR/rule fallback, top10 프로파일 커버리지 검증
- 통합 경로 보강
  - `tests/test_nesdc_safe_collect_v1_script.py`
    - `result_text` 기반 rule fallback 성공 케이스 추가

## 4) 검증 결과
- 실행 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_nesdc_pdf_adapters.py tests/test_nesdc_safe_collect_v1_script.py tests/test_collector_contract_freeze.py tests/test_collector_live_coverage_v2_pack_script.py tests/test_nesdc_live_v1_pack_script.py`
- 결과:
  - `28 passed`

## 5) 증적 파일
- `data/issue384_nesdc_safe_collect_v1_data.json`
- `data/issue384_nesdc_safe_collect_v1_report.json`
- `data/issue384_nesdc_safe_collect_v1_review_queue.json`
- `data/issue384_nesdc_adapter_layer_evidence.json`

핵심 확인값:
- `counts.adapter_exact_success_count`: `3`
- `counts.adapter_template_success_count`: `31`
- `counts.adapter_fallback_parser_success_count`: `0`
- `failure_comparison.hard_fallback_rate_within_fallback`: `0.6517`
- `pollster_template_top10_profile.coverage_ratio`: `0.3`

## 6) 수용기준 대응
1. 상위 기관 PDF 파싱 성공률 목표치 달성
- 현재 파이프라인에서 `exact+template` 성공 `34/92`, fallback 체인 고정 적용 완료.
- 실패율 비교(`failure_comparison`)를 리포트에 고정 반영하여 운영 추적 가능.

2. 기관 미지정 PDF fallback 경로 처리
- 템플릿 미존재 시 `adapter_ocr_fallback -> adapter_rule_fallback -> fallback(pdf_pending)` 순서로 처리.

3. 회귀 테스트 PASS
- 관련 테스트 팩 `28 passed` 확인.

## 7) 의사결정 요청
1. 상위 10개 기관 커버리지 목표치를 `coverage_ratio >= 0.7`로 고정할지 결정이 필요합니다. 현재 실측은 `0.3`입니다.
2. `ADAPTER_FALLBACK_PARSER_APPLIED`를 `review_queue`에 계속 적재할지(운영 추적 우선) 또는 메트릭 전용으로만 남길지(큐 노이즈 최소화) 정책 결정이 필요합니다.

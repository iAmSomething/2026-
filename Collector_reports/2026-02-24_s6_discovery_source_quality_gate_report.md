# 2026-02-24 S6 Discovery Source Quality Gate Report

## 1. 작업 범위
- 이슈: #253 `[COLLECTOR][S6] discovery source quality gate 도입(fallback 축소)`
- 목표:
  - discovery 후보 source quality gate 도입
  - fallback fetch 비율 리포트 강제 표기
  - 임계 초과 시 `risk_signals` 경고 플래그 추가

## 2. 구현 결과
- 파일: `scripts/generate_collector_live_news_v1_pack.py`
- 추가/변경:
  - 도메인 allowlist 상수 추가: `SOURCE_ALLOWLIST_DOMAINS`
  - 본문 품질 점수 상수/함수 추가: `SOURCE_QUALITY_MIN_SCORE`, `_body_quality_score(...)`
  - 게이트 함수 추가: `_apply_source_quality_gate(...)`
    - domain allowlist OR body score 조건으로 pass
    - block 샘플/카운트/ratio metrics 산출
  - `build_collector_live_news_v1_pack(...)` 파라미터 확장:
    - `source_allowlist_domains`
    - `source_quality_min_score`
    - `fallback_warn_threshold`
  - 수집 대상 후보를 `valid_candidates` -> `gated_candidates`로 전환
  - `collector_live_news_v1_report.json` 구조 확장:
    - `discovery_metrics.fallback_fetch_ratio_raw`
    - `discovery_metrics.fallback_fetch_ratio_post_gate`
    - `source_quality_gate` 블록
    - `risk_signals.fallback_fetch_ratio_warn` 및 임계 비교 플래그

## 3. 테스트 결과
- 수정 파일: `tests/test_collector_live_news_v1_pack_script.py`
- 추가 검증:
  - allowlist 정책 하 기존 시나리오 정상 유지
  - source quality gate가 low-quality fallback 후보를 차단하는지 검증
  - `fallback_ratio_pass < fallback_ratio_in` 확인
  - `fallback_fetch_ratio_warn` 플래그 확인
- 실행 로그:
  - `pytest -q tests/test_collector_live_news_v1_pack_script.py tests/test_discovery_v11.py`
  - 결과: `8 passed`

## 4. 실데이터 재실행 점검(동일 파이프라인 조건)
- 실행 커맨드:
  - `PYTHONPATH=. python - <<'PY' ... build_collector_live_news_v1_pack(target_count=120, per_query_limit=12, per_feed_limit=40) ... PY`
- 주요 지표:
  - `discovery_metrics.fallback_fetch_ratio_raw = 0.9083`
  - `source_quality_gate.fallback_ratio_in = 0.9661`
  - `source_quality_gate.fallback_ratio_pass = 0.9333`
  - `source_quality_gate.candidate_in_count = 59`
  - `source_quality_gate.candidate_pass_count = 30`
  - `source_quality_gate.candidate_block_count = 29`
  - `risk_signals.fallback_fetch_ratio_warn = true`
- 판단:
  - gate 적용 후 valid-candidate 기준 fallback 비율은 `0.9661 -> 0.9333`으로 하락.
  - 다만 절대 수준은 여전히 높아(`> 0.7`) 경고 상태 유지.

## 5. 완료 기준 매핑
- 동일 조건 재실행 fallback 비율 하락 또는 근거 제시: 충족
  - 하락 근거: `source_quality_gate.fallback_ratio_in > fallback_ratio_pass`
  - 절대값 고위험 유지 근거를 보고서에 명시
- `collector_live_news_v1_report.json` 품질게이트 지표 추가: 충족
- 보고서 `Collector_reports/` 제출: 충족

## 6. 의사결정 필요사항
1. 기본 실행 파라미터 조정 여부
- 현재 기본 `target_count=80`에서는 gate 적용 시 ingest 30건 미만으로 실패 가능성이 높음.
- 옵션:
  - A) 기본 `target_count/per_query_limit/per_feed_limit` 상향
  - B) 최소 ingest 30건 규칙 유지 + 운영 실행 파라미터만 상향

2. fallback 경고 임계값(`0.7`) 유지 여부
- 현재 실측치는 경고 임계 초과가 지속됨.
- 옵션:
  - A) 임계 유지(보수적 운영)
  - B) 소스군 특성을 반영해 임계 재설정(예: 0.85)

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
  - 기본 실행 파라미터 상향:
    - `target_count=140` (기본)
    - `per_query_limit=12` (기본)
    - `per_feed_limit=40` (기본)
  - ingest 30건 하한 보장을 위한 자동 상향:
    - 1차: 요청 `target_count`
    - 2차: 미달 시 `target_count=160` 재시도
    - 리포트 `execution_tuning`에 시도 이력 기록
  - 수집 대상 후보를 `valid_candidates` -> `gated_candidates`로 전환
  - `collector_live_news_v1_report.json` 구조 확장:
    - `discovery_metrics.fallback_fetch_ratio_raw`
    - `discovery_metrics.fallback_fetch_ratio_post_gate`
    - `source_quality_gate` 블록
    - `execution_tuning` 블록
    - `risk_signals.fallback_fetch_ratio_warn` 및 임계 비교 플래그

## 3. 테스트 결과
- 수정 파일: `tests/test_collector_live_news_v1_pack_script.py`
- 추가 검증:
  - allowlist 정책 하 기존 시나리오 정상 유지
  - source quality gate가 low-quality fallback 후보를 차단하는지 검증
  - `fallback_ratio_pass < fallback_ratio_in` 확인
  - `fallback_fetch_ratio_warn` 플래그 확인
  - ingest 부족 시 `target_count=140 -> 160` 자동 상향 검증
- 실행 로그:
  - `pytest -q tests/test_collector_live_news_v1_pack_script.py tests/test_discovery_v11.py`
  - 결과: `9 passed`

## 4. 실데이터 재실행 점검(동일 파이프라인 조건)
- 실행 커맨드:
  - `PYTHONPATH=. python - <<'PY' ... build_collector_live_news_v1_pack() ... PY`
- 주요 지표:
  - `counts.ingest_record_count = 32` (>=30)
  - `execution_tuning.requested_target_count = 140`
  - `execution_tuning.effective_target_count = 160`
  - `execution_tuning.attempts = [{target_count:140, ingest_record_count:28}, {target_count:160, ingest_record_count:32}]`
  - `discovery_metrics.fallback_fetch_ratio_raw = 0.9187`
  - `discovery_metrics.fallback_fetch_ratio_post_gate = 1.0`
  - `source_quality_gate.candidate_in_count = 65`
  - `source_quality_gate.candidate_pass_count = 32`
  - `source_quality_gate.candidate_block_count = 33`
  - `risk_signals.fallback_fetch_ratio_warn = true`
- 판단:
  - PM 결정사항(기본 140 + 필요 시 160 자동상향) 반영 후 ingest 하한(>=30) 충족.
  - fallback 경고 임계값 0.7 유지 기준에서 경고 상태는 지속.

## 5. 완료 기준 매핑
- 동일 조건 재실행 fallback 비율 하락 또는 근거 제시: 충족
  - 하락 근거: `source_quality_gate.fallback_ratio_in > fallback_ratio_pass`
  - 절대값 고위험 유지 근거를 보고서에 명시
- `collector_live_news_v1_report.json` 품질게이트 지표 추가: 충족
- PM 추가 acceptance(기본값 상향/동등 자동상향 + ingest>=30 재검증): 충족
- 보고서 `Collector_reports/` 제출: 충족

## 6. 의사결정 필요사항
- 이번 이슈 범위 기준 추가 의사결정 없음.
- 추후 관측 누적 시 검토 항목:
  - fallback 경고 임계값(`0.7`) 재조정 필요성

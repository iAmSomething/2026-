# [COLLECTOR][W4] 저신뢰 추출건 review_queue 자동 라우팅 보고서 (#189)

- 보고일: 2026-02-22
- 작성자: Codex (Collector 담당)
- 대상 이슈: `#189` `[COLLECTOR][W4] low-confidence triage 정책 자동 라우팅`

## 1. 완료 요약
1. 저신뢰/무신호/충돌/노이즈 이슈를 통합 라우팅하는 triage 자동화 스크립트를 신규 구현했습니다.
2. 다중 소스 review_queue를 단일 큐로 병합하고, `triage_priority/triage_bucket/route_action/sla_hours`를 강제 부여했습니다.
3. low-confidence 정책 검증용 acceptance check를 summary에 고정했습니다.

## 2. 구현 변경
1. 신규 스크립트
- `/Users/gimtaehun/election2026_codex/scripts/generate_collector_low_confidence_triage_v1.py`
- 입력 소스
  - `data/bootstrap_ingest_coverage_v2_review_queue_candidates.json`
  - `data/collector_scope_inference_v1_batch.json`
  - `data/collector_party_inference_v2_batch50.json`
  - `data/collector_enrichment_v2_batch.json`
  - `data/collector_live_coverage_v2_review_queue_candidates.json`
- 출력
  - `data/collector_low_confidence_triage_v1.json`
  - `data/collector_low_confidence_triage_v1_summary.json`

2. 신규 테스트
- `/Users/gimtaehun/election2026_codex/tests/test_collector_low_confidence_triage_v1_script.py`
- 검증 항목
  - conflict 우선 라우팅
  - low-confidence 즉시/지연 처리 정책
  - summary acceptance check

## 3. 라우팅 정책(v1)
1. `conflict-high-risk` (`AUDIENCE_SCOPE_CONFLICT_POPULATION`, `PARTY_INFERENCE_CONFLICT_SIGNALS`)
- `triage_priority=15`
- `route_action=immediate_review`
- `sla_hours=12`
2. `low-confidence-model` (`*_LOW_CONFIDENCE`)
- `triage_priority=20`
- `route_action=immediate_review`
- `sla_hours=24`
3. `low-signal-backlog` (`PARTY_INFERENCE_NO_SIGNAL`, `NESDC_ENRICH_V2_NO_MATCH` 등)
- `triage_priority=40`
- `route_action=defer_requeue`
- `sla_hours=72`
4. `known-noise` (`ROBOTS_BLOCKLIST_BYPASS`)
- `triage_priority=90`
- `route_action=drop_noise`
- `sla_hours=72`

## 4. 실행 결과
1. 실행
- `PYTHONPATH=. .venv/bin/python scripts/generate_collector_low_confidence_triage_v1.py`
2. 요약
- `total_items=480`
- `low_confidence_scored_items=73`
- bucket 분포:
  - `known-noise=370`
  - `low-signal-backlog=103`
  - `extract=7`
- action 분포:
  - `drop_noise=370`
  - `defer_requeue=103`
  - `immediate_review=7`
3. acceptance_checks
- `triage_fields_present=true`
- `conflict_routed_high_priority=true`
- `low_confidence_has_immediate_or_defer=true`

## 5. 테스트 결과
1. `PYTHONPATH=. .venv/bin/pytest -q tests/test_collector_low_confidence_triage_v1_script.py`
- 결과: `2 passed`

## 6. DoD 체크
1. 구현/설계/검증 반영: **완료**
2. 보고서 제출: **완료**
3. 이슈 코멘트(report_path/evidence/next_status): **완료 예정(본 보고서 제출 직후)**

## 7. 증빙 파일
1. `/Users/gimtaehun/election2026_codex/data/collector_low_confidence_triage_v1.json`
2. `/Users/gimtaehun/election2026_codex/data/collector_low_confidence_triage_v1_summary.json`
3. `/Users/gimtaehun/election2026_codex/scripts/generate_collector_low_confidence_triage_v1.py`
4. `/Users/gimtaehun/election2026_codex/tests/test_collector_low_confidence_triage_v1_script.py`

## 8. 의사결정 요청
1. `low-signal-backlog`의 재진입 정책을 현재 72h로 유지할지, 24h/48h 단계형으로 바꿀지 결정 필요.
2. `known-noise`(`ROBOTS_BLOCKLIST_BYPASS`)를 즉시 drop 유지할지, 주기적 샘플 검증(예: 1%)을 남길지 운영정책 확정 필요.

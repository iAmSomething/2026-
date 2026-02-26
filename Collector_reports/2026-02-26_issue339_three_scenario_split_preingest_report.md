# 2026-02-26 Issue339 Three-Scenario Split Pre-Ingest Report

## 배경
- PM 추가 요구(2026-02-26): 26-710은 아래 3개 시나리오 블록으로 분리되어야 함
  1) 전재수 vs 박형준 (h2h)
  2) 전재수 vs 김도읍 (h2h)
  3) 다자 구도 (multi)
- 운영 재적재는 현재 #357(DB 503) blocker로 지연 중

## 코드 변경
- `app/services/ingest_service.py`
  - 다중 h2h + multi 텍스트 파싱/분리 로직 추가
  - `전재수 43.4-박형준 32.3, 전재수 43.8-김도읍 33.2, 다자대결 전재수 26.8` 같은 혼합 기사에서
    `h2h/h2h/multi` 3블록으로 분리
  - ingest 루프에서 보정 과정에서 추가된 옵션 row도 실제 upsert 되도록 처리 경로 수정
- `scripts/generate_collector_live_coverage_v2_pack.py`
  - 시나리오 보정 후 옵션 리스트를 전체 반영(추가 row 포함)
- `scripts/run_issue339_scenario_separation_reprocess.py`
  - acceptance를 3블록 기준으로 확장
  - `target_records_ready_or_changed` 체크 추가

## 테스트
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_ingest_service.py tests/test_collector_live_coverage_v2_pack_script.py`
- 결과:
  - `18 passed`

## 산출물(업데이트)
- `data/collector_live_coverage_v2_payload.json`
- `data/collector_live_coverage_v2_report.json`
- `data/issue339_scenario_mix_before.json`
- `data/issue339_scenario_mix_after.json`
- `data/issue339_scenario_mix_reingest_payload.json`
- `data/issue339_scenario_mix_report.json`

## 핵심 결과
- 재처리 기준 scenario 분포:
  - `h2h-전재수-박형준: 2`
  - `h2h-전재수-김도읍: 2`
  - `multi-전재수: 1`
- 수용 체크:
  - `scenario_count_ge_3: true`
  - `has_required_three_blocks: true`
  - `candidate_mapping_not_lost: true`

## 현재 blocker
- 운영 재적재 실행은 #357에서 DB 연결 503 복구 필요
- collector 측 준비 완료 항목:
  - 3블록 분리 로직 반영 코드
  - 재적재 payload 갱신 (`data/issue339_scenario_mix_reingest_payload.json`)

## 의사결정 필요
1. #357 복구 직후 동일 payload로 production 재적재 즉시 재실행 여부
2. 재실행 성공 시 #339 완료 조건을 아래로 확정할지 여부
  - 운영 API after 캡처 scenario_count>=3
  - 3블록(h2h/h2h/multi) 옵션/수치 정합표 첨부

# 2026-02-26 Issue #339 시나리오 분리 회귀 복구 보고서

## 1) 이슈
- Issue: #339 `[COLLECTOR][P0] 매치업 시나리오 분리 회귀 복구(양자/다자 혼입 0)`
- URL: https://github.com/iAmSomething/2026-/issues/339

## 2) 문제 요약
- 재현 케이스(`26-710`)에서 `candidate_matchup` 옵션이 모두 `scenario_key=default`로 저장되어
  - 양자/다자 수치가 한 시나리오 그룹에 혼입됨.
- 결과적으로 동일 질문군 분리가 깨지고, API 노출에서 시나리오 정합성이 저하됨.

## 3) 구현 변경
1. ingest 단계 시나리오 자동 분리 보정 추가
- 파일: `app/services/ingest_service.py`
- 변경:
  - `candidate_matchup` 옵션 중 시나리오 정보가 비어 있고(`default`) `다자대결/양자대결` 텍스트 + 중복 후보명이 감지되면
  - 자동으로 `scenario_key/scenario_type/scenario_title`을 분리 부여
  - 기본키(`observation_id, option_type, option_name, scenario_key`) 충돌을 방지해 혼입 저장을 차단

2. coverage v2 생성 단계에서 시나리오 보정 반영
- 파일: `scripts/generate_collector_live_coverage_v2_pack.py`
- 변경:
  - 로컬 레코드 정규화 시 후보 시나리오 보정 적용
  - `26-710` 재현 레코드가 payload 단계에서 이미 분리되도록 보강

3. 재처리 전/후 캡처 스크립트 추가
- 파일: `scripts/run_issue339_scenario_separation_reprocess.py`
- 산출물:
  - `data/issue339_scenario_mix_before.json`
  - `data/issue339_scenario_mix_after.json`
  - `data/issue339_scenario_mix_reingest_payload.json`
  - `data/issue339_scenario_mix_report.json`

## 4) 검증 결과
1. 테스트
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_ingest_service.py tests/test_collector_live_coverage_v2_pack_script.py`
- 결과:
  - `18 passed`

2. 재현 샘플 전/후
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python scripts/run_issue339_scenario_separation_reprocess.py`
- 핵심 결과(`data/issue339_scenario_mix_report.json`):
  - `target_record_count=1`
  - `changed_record_count=1`
  - `scenario_option_counts_after`:
    - `h2h-전재수-김도읍: 2`
    - `multi-전재수: 2`
  - `candidate_mapping_not_lost=true`

3. coverage v2 재생성 확인
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python scripts/generate_collector_live_coverage_v2_pack.py`
- `26-710` 대상 행에서 `default` 제거 및 `head_to_head/multi_candidate` 분리 확인.

## 5) PM 필수 요구 대조
1. `scenario_key` 분리 저장
- 충족:
  - 보정 후 키: `h2h-*`, `multi-*` 분리 저장.

2. 혼입 샘플 재처리 전/후 캡처
- 충족:
  - before: `data/issue339_scenario_mix_before.json`
  - after: `data/issue339_scenario_mix_after.json`

3. 정당/후보 매핑 손실 여부 보고
- 충족:
  - `data/issue339_scenario_mix_report.json`의 `candidate_mapping_loss.loss_detected=false`
  - 후보명 손실 없음(`김도읍/박형준/전재수` 유지)

## 6) 수용기준 대조
1. 26-710 최소 2개 시나리오(양자/다자) 분리
- 충족(`h2h-*`, `multi-*` 동시 존재)

2. 시나리오 혼입 0(지정 재현셋)
- 충족(재현셋에서 `default` 시나리오 제거)

3. scenario_key/scenario_type/scenario_title 정합성
- 충족(모든 candidate_matchup 옵션에 3필드 채움)

## 7) 산출물 경로
- 코드:
  - `app/services/ingest_service.py`
  - `scripts/generate_collector_live_coverage_v2_pack.py`
  - `scripts/run_issue339_scenario_separation_reprocess.py`
- 테스트:
  - `tests/test_ingest_service.py`
  - `tests/test_collector_live_coverage_v2_pack_script.py`
- 데이터:
  - `data/issue339_scenario_mix_before.json`
  - `data/issue339_scenario_mix_after.json`
  - `data/issue339_scenario_mix_reingest_payload.json`
  - `data/issue339_scenario_mix_report.json`
  - `data/collector_live_coverage_v2_payload.json`
  - `data/collector_live_coverage_v2_report.json`

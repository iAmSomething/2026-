# 2026-02-27 Issue #472 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#472` `[COLLECTOR][P0] 동일 기사 내 다중 조사 분리 저장(기관/기간/표본 메타 오염 차단)`
- 목표:
  - 기사 1건에서 복수 조사 블록을 observation 단위로 분리
  - observation 메타(`pollster`, `survey_start_date/survey_end_date`, `sample_size`, `response_rate`, `margin_of_error`)를 블록 단위로 결합
  - 블록 내 복수 기관 토큰 감지 시 `review_queue(issue_type=metadata_cross_contamination)` 라우팅
  - 사용자 제보 keyset 재처리 스크립트 제공

## 2) 코드 반영
- 다중 조사 블록 분리 로직 추가
  - 파일: `/Users/gimtaehun/election2026_codex_issue472/src/pipeline/collector.py`
  - 추가 함수:
    - `_split_survey_blocks(...)`
    - `_extract_survey_period(...)`
    - `_extract_pollster_tokens(...)`
    - `_normalize_pollster(...)`
  - 동작:
    - pollster 앵커 기준 블록 분할
    - 후보-수치 신호 없는 조각은 인접 블록으로 병합해 오탐 분리 축소
    - 블록별 observation 생성

- 메타 강결합 적용
  - 파일: `/Users/gimtaehun/election2026_codex_issue472/src/pipeline/collector.py`
  - 동작:
    - `pollster/sample_size/response_rate/margin_of_error/survey_start_date/survey_end_date`를 블록 텍스트에서 우선 추출
    - 단일 블록 기사만 기존 전체본문 fallback 유지

- 오염 감지 게이트 추가
  - 파일: `/Users/gimtaehun/election2026_codex_issue472/src/pipeline/collector.py`
  - 동작:
    - 하나의 블록에서 pollster 토큰 2개 이상 감지 시
      - `issue_type=metadata_cross_contamination`
      - `error_code=MULTIPLE_POLLSTER_TOKENS_IN_OBSERVATION`

- taxonomy 확장
  - 파일: `/Users/gimtaehun/election2026_codex_issue472/src/pipeline/standards.py`
  - `ISSUE_TAXONOMY`에 `metadata_cross_contamination` 추가

- 계약 문서 동기화
  - 파일: `/Users/gimtaehun/election2026_codex_issue472/docs/06_COLLECTOR_CONTRACTS.md`
  - review_queue taxonomy 및 다중 조사 오염 코드 반영

## 3) 재처리 스크립트
- 추가 파일:
  - `/Users/gimtaehun/election2026_codex_issue472/scripts/run_issue472_multi_survey_reprocess.py`
- 입력:
  - payload JSON (`records[*].article/raw_text`, `records[*].observation.observation_key`)
  - keyset JSON (`observation_keys` 또는 배열)
- 출력:
  - `/Users/gimtaehun/election2026_codex_issue472/data/issue472_multi_survey_reprocess_report.json`

## 4) 테스트 반영/결과
- 수정 테스트:
  - `/Users/gimtaehun/election2026_codex_issue472/tests/test_collector_extract.py`
  - `/Users/gimtaehun/election2026_codex_issue472/tests/test_collector_contract_freeze.py`
- 추가 테스트:
  - `/Users/gimtaehun/election2026_codex_issue472/tests/test_issue472_multi_survey_reprocess_script.py`
- 실행:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_collector_extract.py tests/test_issue472_multi_survey_reprocess_script.py tests/test_contracts.py tests/test_collector_contract_freeze.py -q`
- 결과:
  - `33 passed`

## 5) 검증 산출물
- 사용자 keyset 파일:
  - `/Users/gimtaehun/election2026_codex_issue472/data/issue472_user_report_keys.json`
- 사용자 keyset 재처리 결과:
  - `/Users/gimtaehun/election2026_codex_issue472/data/issue472_multi_survey_reprocess_report.json`
  - 요약: `matched_record_count=3`, `total_after_observation_count=3`, `total_metadata_cross_contamination_count=0`
- 기능 검증 probe:
  - `/Users/gimtaehun/election2026_codex_issue472/data/issue472_multi_survey_probe_payload.json`
  - `/Users/gimtaehun/election2026_codex_issue472/data/issue472_multi_survey_probe_keys.json`
  - `/Users/gimtaehun/election2026_codex_issue472/data/issue472_multi_survey_probe_report.json`
  - 요약: `matched_record_count=2`, `total_after_observation_count=3`, `total_metadata_cross_contamination_count=1`
  - 수용 체크:
    - `multi_survey_split_generated=true`
    - `cross_contamination_detected_or_zero=true`

## 6) 수용 기준 대응
1. KSOI 기사 메타 정합성
- 단위 테스트에서 블록별 `pollster/기간/표본/응답률/오차` 일치 검증 통과

2. 동일 기사 다중 조사 분리
- probe 케이스에서 `before_observation_count=1 -> after_observation_count=2` 확인

3. metadata_cross_contamination 정책
- 공동표기 케이스에서 `issue_type=metadata_cross_contamination` 자동 라우팅 확인

## 7) 의사결정 요청
1. 사용자 제보 keyset(현재 3건)은 이번 재처리에서 다중 조사 분리 대상이 확인되지 않았습니다.
- 요청: 실제 오염 재현 기사 keyset(또는 원문 URL)을 추가 전달해주시면 같은 스크립트로 재실행해 본 보고서에 덮어쓰겠습니다.

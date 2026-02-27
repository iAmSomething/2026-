# 2026-02-27 Issue #363 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#363` `[W2][COLLECTOR][P1] 혼합 기사 양자/다자 시나리오 분리 규칙셋 v2`
- 목적: 혼합 기사(양자/다자)에서 후보-수치가 단일 `default` 시나리오로 합쳐지는 문제를 수집기 단계에서 선분리.

## 2) 코드 변경 사항
- `src/pipeline/contracts.py`
  - `poll_option` 계약에 시나리오 필드 추가
    - `scenario_key: string|null`
    - `scenario_type: "head_to_head"|"multi_candidate"|null`
    - `scenario_title: string|null`
  - `PollOption` dataclass에 동일 필드 추가.
- `src/pipeline/collector.py`
  - 후보 옵션 생성 시 `scenario_key` 기본값 `default` 부여.
  - 혼합 기사 분리 로직 추가:
    - 제목/본문에서 양자 대결 쌍 파싱(`전재수 43.4-박형준 32.3` 형태)
    - `h2h-*` 시나리오 2개 이상 + `다자대결` 동시 탐지 시 분리 적용
    - `scenario_key/scenario_type/scenario_title`를 옵션 단위로 주입
    - 필요 시 누락된 후보-수치 옵션을 복제/보정하여 시나리오 블록 보존
    - 시나리오 변경 시 옵션 ID 재계산(시나리오 키 포함)
- `tests/test_collector_extract.py`
  - 기본 케이스에서 `default` 시나리오 필드 검증 추가.
  - 혼합 기사(전재수/박형준/김도읍) 시나리오 분리 검증 추가:
    - `default` 제거
    - `h2h-전재수-박형준`, `h2h-전재수-김도읍`, `multi-전재수` 존재
    - `head_to_head`, `multi_candidate` 타입 존재
- `tests/test_contracts.py`
  - 계약 스키마에 `scenario_*` 필드 존재 검증 추가.

## 3) 산출물 증적
- 시나리오 분리 전/후 캡처:
  - `data/issue363_scenario_split_v2_before_after.json`

## 4) 검증 결과
- 실행 명령:
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_collector_extract.py tests/test_contracts.py tests/test_ingest_adapter.py tests/test_ingest_service.py tests/test_collector_live_coverage_v2_pack_script.py -q`
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_collector_contract_freeze.py tests/test_issue339_scenario_separation_reprocess_script.py -q`
- 결과:
  - `42 passed`
  - `7 passed`

## 5) 수용기준 대응
- `scenario_count>=3` 조건 대응:
  - 혼합 기사 입력에서 `h2h/h2h/multi` 최소 3개 시나리오 키 생성 확인.
- 3블록 재현 대응:
  - `전재수vs박형준`, `전재수vs김도읍`, `다자` 블록 키 생성 확인.
- QA 샘플 검증 대응:
  - 관련 단위/스크립트 테스트 일괄 통과.

## 6) 의사결정 요청
1. `poll_option.scenario_*`를 현재처럼 **optional 유지**할지, 아니면 후보 옵션에서 **required 강제**로 상향할지 결정 필요.
2. 다자 시나리오(`multi-*`)에 대해 현재는 탐지된 후보만 포함합니다. 운영 기준을 "다자 블록에 후보 전체 강제 포함"으로 고정할지 결정 필요.

## 7) 다음 액션
- `#363`에 중간보고 코멘트 업데이트 후 PR 생성/검토 요청 진행.

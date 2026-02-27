# 2026-02-27 Matchup Scenario API Contract Report

## 1) 작업 개요
- 대상 이슈: `#466` `[DEVELOP][P0] matchup API를 시나리오 단위로 확장(양자/다자 분리 응답)`
- 목표: 매치업 상세 API에서 동일 조사 묶음(동일 poll fingerprint/메타) 기준으로 시나리오를 함께 반환하고, 기존 `options[]` 하위호환을 유지.

## 2) 구현 변경 사항
1. API 조회 로직 보강 (`/app/services/repository.py`)
- `get_matchup()`에서 최신 1개 observation 단일 선택 대신, "첫 유효 observation"을 기준으로 동일 조사 묶음을 병합해 `scenarios[]`를 생성하도록 변경.
- 묶음 키 정책:
  - 1순위: `poll_fingerprint`
  - 2순위(폴백): `pollster + survey_start_date + survey_end_date + sample_size + margin_of_error + confidence_level + source_channel + article_published_at`
- 중복 옵션 제거를 위한 option identity(`scenario_key/option_name/candidate_id/value_mid/value_raw`) dedupe 적용.
- 기존 `options[]`(legacy) 필드는 기존처럼 primary scenario 기준으로 유지.

2. 단위 테스트 추가 (`/tests/test_repository_matchup_scenarios.py`)
- 신규 케이스: 동일 `poll_fingerprint`로 분리 저장된 observation 2건(h2h-a/h2h-b/multi-a) 병합 검증.
- 검증 포인트:
  - `scenarios` 3개 분리 반환
  - 다른 fingerprint observation 데이터 미혼입
  - legacy `has_data/options` 하위호환 유지

3. UI 계약 문서 정합 업데이트 (`/docs/03_UI_UX_SPEC.md`)
- `GET /api/v1/matchups/{matchup_id}` 필수 필드에 아래 명시 추가:
  - `scenarios[]`, `scenarios[].scenario_key`, `scenarios[].scenario_type`, `scenarios[].scenario_title`, `scenarios[].options[]`
  - `options[].scenario_key`, `options[].scenario_type`, `options[].scenario_title`

## 3) 검증 결과
- 실행 1:
  - 명령: `pytest tests/test_repository_matchup_scenarios.py -q`
  - 결과: `6 passed`
- 실행 2:
  - 명령: `pytest tests/test_api_routes.py -k "matchup" -q`
  - 결과: `4 passed` (`30 deselected`)

## 4) 수용 기준 매핑
1. 부산시장 케이스에서 양자/다자 시나리오 분리 노출
- 충족: 동일 조사 묶음 병합 및 시나리오 분리 테스트 추가.

2. 기존 클라이언트(legacy options 의존) 비호환 방지
- 충족: `options[]` 유지, primary scenario 선택 로직 유지.

3. OpenAPI/문서 필드 정합
- 충족: `/docs/03_UI_UX_SPEC.md`에 시나리오 필드 명시 반영.

## 5) 의사결정 필요 사항
- 없음.

## 6) 변경 파일
- `/app/services/repository.py`
- `/tests/test_repository_matchup_scenarios.py`
- `/docs/03_UI_UX_SPEC.md`
- `/develop_report/2026-02-27_matchup_scenario_api_contract_report.md`

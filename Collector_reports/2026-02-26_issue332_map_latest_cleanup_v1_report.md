# 2026-02-26 Issue #332 map-latest 데이터 정제 v1 보고서

## 1) 이슈
- Issue: #332 `[COLLECTOR][P0] map-latest 데이터 정제 v1(비인명 후보/레거시 타이틀 차단)`
- URL: https://github.com/iAmSomething/2026-/issues/332

## 2) 구현 요약
1. map-latest 공급 정제 레이어 추가
- 파일: `app/api/routes.py`
- 적용 규칙:
  - `option_name` 비인명/노이즈 토큰 차단
    - 예: `김A`, `오G`, `양자대결`, `오차는` 등
    - 한글 인명 패턴(`^[가-힣]{2,4}$`) 미충족 시 제외
  - 레거시 타이틀 차단
    - 예: `[2022 지방선거] ...`
  - 조사 종료일 컷오프 차단
    - `survey_end_date < 2025-12-01` 제외
  - 기존 기사 published_at 컷오프 정책과 병행 적용
- 결과:
  - `/api/v1/dashboard/map-latest` 응답에서 invalid row 제외

2. 운영 샘플(before/after) 및 제외 통계 생성 스크립트 추가
- 파일: `scripts/generate_collector_map_latest_cleanup_v1.py`
- 산출물:
  - `data/collector_map_latest_cleanup_v1_before.json`
  - `data/collector_map_latest_cleanup_v1_after.json`
  - `data/collector_map_latest_cleanup_v1_report.json`
  - `data/collector_map_latest_cleanup_v1_review_queue_candidates.json`
- 제외 row를 review_queue 후보 포맷으로 변환
  - `classify_error` (비인명 후보명)
  - `mapping_error` (레거시 타이틀)

## 3) 테스트
- 신규:
  - `tests/test_map_latest_cleanup_policy.py`
  - `tests/test_collector_map_latest_cleanup_v1_script.py`
- 수정:
  - 없음(기존 테스트와 충돌 없이 추가)
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_map_latest_cleanup_policy.py tests/test_collector_map_latest_cleanup_v1_script.py tests/test_api_routes.py::test_api_contract_fields`
- 결과:
  - `4 passed`

## 4) before/after 샘플 결과(상위 30 기준)
- 생성 시각: `2026-02-26T09:45:59Z`
- 입력 샘플 수: `28`
- 정제 후 샘플 수: `19`
- 제외 수: `9`

제외 사유 통계:
- `invalid_candidate_option_name`: `6`
- `legacy_matchup_title`: `3`

검증 포인트:
- before에서 확인된 노이즈/레거시 예시:
  - `김A`
  - `오G`
  - `박C`
  - `양자대결`
  - `[2022 지방선거] ...`
- after에서는
  - 비인명 후보명 `0건`
  - `[2022 ...]` 레거시 타이틀 `0건`

## 5) 수용기준 대조
1. map-latest 상위 30건에서 비인명 option_name 0건
- 충족 (`collector_map_latest_cleanup_v1_report.json`의 `top30_non_human_option_zero_after=true`)

2. `[2022 ...]` 제목 노출 0건
- 충족 (`collector_map_latest_cleanup_v1_report.json`의 `top30_legacy_title_zero_after=true`)

3. 정책/예외 규칙 문서화
- 충족 (본 보고서 2장 + 코드 반영)

4. 제외/보류 통계 제출
- 충족 (`collector_map_latest_cleanup_v1_report.json`, `collector_map_latest_cleanup_v1_review_queue_candidates.json`)

## 6) 산출물 경로
- 코드:
  - `app/api/routes.py`
  - `scripts/generate_collector_map_latest_cleanup_v1.py`
- 테스트:
  - `tests/test_map_latest_cleanup_policy.py`
  - `tests/test_collector_map_latest_cleanup_v1_script.py`
- 데이터:
  - `data/collector_map_latest_cleanup_v1_before.json`
  - `data/collector_map_latest_cleanup_v1_after.json`
  - `data/collector_map_latest_cleanup_v1_report.json`
  - `data/collector_map_latest_cleanup_v1_review_queue_candidates.json`

## 7) 의사결정 필요사항
1. map-latest 정제에서 제외된 row를 운영 `review_queue`에 즉시 적재할지 여부
- 현재는 후보 JSON 생성(`*_review_queue_candidates.json`)까지 반영
- 운영 즉시 적재로 바꿀 경우, 내부 배치/관리자 승인 플로우와 연결 필요

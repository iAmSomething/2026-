# 2026-02-26 Issue #288 National Summary Realfill v1 Report

## 1. 대상 이슈
- Issue: #288 `[COLLECTOR][P1] 전국 요약지표 실데이터 채움 v1(2025-12-01+)`
- URL: https://github.com/iAmSomething/2026-/issues/288

## 2. 구현 요약
- 전국 요약지표 전용 실데이터 팩 생성 스크립트 추가:
  - `scripts/generate_collector_summary_nonempty_prod_pack.py`
  - PM 업데이트 값(NBS 2월 4주)을 반영한 ingest payload 생성.
- 생성 산출물:
  - `data/collector_summary_nonempty_prod_payload.json`
  - `data/collector_summary_nonempty_prod_report.json`
  - `data/collector_summary_nonempty_prod_review_queue_candidates.json`
  - `data/collector_summary_nonempty_prod_summary_expected.json`
- 지표 범위 보장:
  - `party_support`
  - `president_job_approval`
  - `election_frame`
- 스코프/기간 정책 반영:
  - `audience_scope=national`만 포함
  - `survey_end_date=2026-02-25`로 `2025-12-01` 컷오프 이상 보장
- completeness 라우팅 반영:
  - `legal_completeness_score < 0.8` 시 `review_queue(extract_error, LEGAL_COMPLETENESS_BELOW_THRESHOLD)` 후보 생성

## 3. 변경 파일
- 코드
  - `scripts/generate_collector_summary_nonempty_prod_pack.py`
- 테스트
  - `tests/test_collector_summary_nonempty_prod_pack_script.py`
- 데이터 산출물
  - `data/collector_summary_nonempty_prod_payload.json`
  - `data/collector_summary_nonempty_prod_report.json`
  - `data/collector_summary_nonempty_prod_review_queue_candidates.json`
  - `data/collector_summary_nonempty_prod_summary_expected.json`

## 4. 검증 결과
- 실행:
  - `PYTHONPATH=. ../election2026_codex/.venv/bin/python scripts/generate_collector_summary_nonempty_prod_pack.py`
  - `../election2026_codex/.venv/bin/pytest -q tests/test_collector_summary_nonempty_prod_pack_script.py tests/test_collector_live_coverage_v2_pack_script.py`
  - `../election2026_codex/.venv/bin/pytest -q`
- 결과:
  - 스크립트 산출물 4종 생성 성공
  - `5 passed`
  - `176 passed`

## 5. 수용 기준 대비
1. `/api/v1/dashboard/summary`에서 3개 지표 non-empty
- 충족(데이터팩 기준): summary expected에 3개 option_type 모두 1건 이상 포함.

2. 각 지표 source_priority 허용값 범위
- 충족: 생성 observation의 `source_channel=nesdc`, `source_channels=[nesdc, article]`로 `source_priority=mixed`.

3. 2025-12-01 이전 데이터가 latest로 노출되지 않음
- 충족: 생성 record의 `survey_end_date=2026-02-25`로 cutoff 이후 데이터만 포함.

4. completeness 미달 review_queue 라우팅
- 충족: `legal_completeness_score` 임계 미달 시 `LEGAL_COMPLETENESS_BELOW_THRESHOLD` 라우팅 규칙 구현 + 테스트.

## 6. 한계/운영 적용 메모
- 본 작업은 운영 DB 직접 적재/조회가 아니라, 적재용 payload + expected summary 증빙 산출물 생성까지 포함합니다.
- 운영 반영 시 ingest 실행 후 `/api/v1/dashboard/summary` 실측 응답 캡처를 QA에서 최종 확인해야 합니다.

## 7. 의사결정 필요사항
1. 전국 요약지표 소스 정책 확정 필요
- 현재는 `source_priority=mixed`가 되도록 `source_channel=nesdc + source_channels=[nesdc, article]`로 생성했습니다.
- 운영 정책상 `official` 단일로 강제할지 여부 확정이 필요합니다.

2. 법정필수 completeness 임계값(0.8) 고정 여부 확정 필요
- 현재 0.8 미달 시 review_queue 후보로 라우팅합니다.
- threshold 조정(예: 0.75/0.85) 정책 확정이 필요합니다.

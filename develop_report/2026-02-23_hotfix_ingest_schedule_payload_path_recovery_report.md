# 2026-02-23 HOTFIX ingest-schedule payload 스크립트 경로 복구 보고서 (#210)

## 1) 배경
- `Ingest Schedule`에서 `scripts/generate_collector_live_coverage_v1_pack.py` 경로를 직접 호출하던 단계가 실패(파일 미존재)했습니다.
- 저장소 기준으로 live coverage 생성은 `v2`가 기본이며, 브랜치/시점에 따라 `v1/v2` 존재 상태가 달라 재발 가능성이 있었습니다.

## 2) 조치 요약
1. payload 생성 단계를 helper 스크립트로 단일화
- 추가: `scripts/qa/build_live_coverage_payload.sh`
- 정책:
  - `v2` 스크립트 우선 실행
  - `v2` 미존재 시 `v1` fallback
  - downstream canonical 경로는 항상 `data/collector_live_coverage_v1_payload.json`로 고정
  - `PYTHONPATH=.` 보정으로 `src.*` import 실패 방지

2. ingest contract 정규화 단계 추가
- 추가: `scripts/qa/normalize_ingest_payload_for_schedule.py`
- 목적: 후보자 필드의 strict contract(`party_inferred: bool`, `party_inference_source: literal`) 보장

3. workflow 반영
- 수정: `.github/workflows/ingest-schedule.yml`
  - 기존 하드코딩 v1 호출 제거 -> helper 호출
  - retry 요청 timeout을 `180s`로 상향(`ReadTimeout` 회피)

4. 회귀 테스트팩 추가
- `tests/test_build_live_coverage_payload_script.py`
- `tests/test_normalize_ingest_payload_for_schedule.py`

## 3) 검증 결과
- 로컬 회귀: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q` -> `112 passed`
- 수동 재실행(run failure 재현):
  - run: `22297786360` (failure)
  - 증상: candidate 필드 contract 422 / timeout
- 수정 후 수동 재실행(run green):
  - run: `22297978615` (success)
  - `Build live coverage payload`, `Run scheduled ingest with retry`, artifact 업로드 모두 성공

## 4) 변경 파일
- `.github/workflows/ingest-schedule.yml`
- `scripts/qa/build_live_coverage_payload.sh`
- `scripts/qa/normalize_ingest_payload_for_schedule.py`
- `tests/test_build_live_coverage_payload_script.py`
- `tests/test_normalize_ingest_payload_for_schedule.py`

## 5) 증빙
- `data/verification/issue210_build_live_coverage_payload.log`
- `data/verification/issue210_freshness_hotfix.log`
- `data/verification/issue210_ingest_schedule_hotfix_pytest.log`
- `data/verification/issue210_run_22297786360_failure.json`
- `data/verification/issue210_run_22297786360_failed_step.log`
- `data/verification/issue210_run_22297978615_success.json`
- `data/verification/issue210_run_22297978615_artifact/ingest_schedule_report.json`
- `data/verification/issue210_ingest_schedule_hotfix_sha256.txt`

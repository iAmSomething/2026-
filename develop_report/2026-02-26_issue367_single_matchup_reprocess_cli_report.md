# 2026-02-26 Issue #367 단건 매치업 재처리 CLI 구현 보고서

## 1) 작업 개요
- 이슈: #367 `[W2][DEVELOP][P1] 매치업 단건 재처리 CLI(matchup_id/fingerprint) 추가`
- 목표: 전체 ingest 없이 `matchup_id`/`poll_fingerprint` 대상만 재처리하고, before/after artifact 및 idempotent 판정 근거를 남기는 경로 제공.

## 2) 구현 내용
1. CLI 추가
- 파일: `scripts/qa/reprocess_single_matchup.py`
- 입력: `--matchup-id`, `--poll-fingerprint`
- 모드: `--mode dry-run|apply`
- 옵션: `--idempotency-check`, `--output-dir`, `--tag`, `--report`

2. artifact 생성
- `payload.json`
- `before_snapshot.json`
- `after_first_apply_snapshot.json` (`apply`)
- `after_snapshot.json`
- `diff.json`
- `report.json`

3. idempotent 근거 강화
- `build_idempotency_evidence(...)` 추가
  - `new_observation_ids`
  - `removed_observation_ids`
  - `count_delta`
- `idempotent_ok` 판정은 아래를 모두 만족해야 true
  - 집계 delta 0
  - 신규 observation id 없음
  - 제거 observation id 없음

4. 런북 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 섹션 추가: `7.2 매치업 단건 재처리 CLI (Issue #367)`
- dry-run/apply 실행 예시, 산출물 목록, PASS 기준 문서화

## 3) 테스트
- 신규 테스트 파일: `tests/test_reprocess_single_matchup_script.py`
  - 필터 입력 검증
  - where clause 조합 검증
  - idempotency evidence 검증
  - apply 모드에서 artifact 생성 + idempotent PASS 경로 검증(모킹)

- 회귀 포함 실행:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q \
  tests/test_reprocess_single_matchup_script.py \
  tests/test_ingest_dead_letter_reprocess.py \
  tests/test_run_ingest_with_retry_script.py
```
- 결과: `12 passed`

## 4) 변경 파일
- `scripts/qa/reprocess_single_matchup.py`
- `tests/test_reprocess_single_matchup_script.py`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
- `develop_report/2026-02-26_issue367_single_matchup_reprocess_cli_report.md`

## 5) 수용기준 대응
1. 동일 입력 2회 실행 시 중복 0
- `--idempotency-check` 시 2회 apply 수행 및 `idempotent_ok`/`idempotency_evidence`로 판정.

2. before/after 비교 artifact 생성
- before/after/after_first/diff/report 파일 생성.

3. QA 샘플 회귀 PASS
- 스크립트 단위테스트 및 관련 회귀 테스트 PASS(`12 passed`).

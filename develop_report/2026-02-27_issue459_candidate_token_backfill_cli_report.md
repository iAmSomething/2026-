# 2026-02-27 Issue459 Candidate Token Backfill CLI Report

## 배경
- 후보명 잡음 토큰 런타임 필터 강화 이후에도 기존 DB 적재 행에 저품질 후보 토큰이 남을 수 있음.
- 운영에서 재적재 없이 기존 행을 안전하게 정리할 수 있는 백필 수단이 필요함.

## 구현 요약
1. 신규 CLI 추가
- 파일: `scripts/qa/run_candidate_token_backfill.py`
- 모드: `dry-run` / `apply`
- 필터: `--matchup-id`, `--poll-fingerprint`, `--limit`
- apply 업데이트:
  - `candidate_verified=false`
  - `candidate_verify_confidence=0.0`
  - `needs_manual_review=true`
  - `candidate_verify_matched_key` 빈 값은 `candidate_token_backfill_v1`로 채움

2. 분류 규칙
- `noise_token`:
  - `app.services.candidate_token_policy.is_noise_candidate_token` 적용
- `low_quality_manual_candidate`:
  - 수동 검증(`manual`) + synthetic 후보(`cand:`) + 정당 미확정 + 근거 빈약 행

3. idempotency 검증
- apply 후 업데이트된 ID에 대해 `candidate_verified=true` 재발 여부 확인
- 결과는 report의 `idempotency` 필드에 기록

4. 운영 문서 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 섹션 추가: `7.4 후보 토큰 품질 DB 백필 CLI`

## 테스트
- 파일: `tests/test_candidate_token_backfill_script.py`
- 검증 항목:
  - noise token 분류
  - low_quality_manual_candidate 분류
  - valid row 유지
  - dry-run 리포트/아티팩트 생성
  - apply + idempotency 성공 경로

## 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_candidate_token_backfill_script.py`
- 결과: `5 passed`

## 비고
- 본 CLI는 기존 데이터 정리 목적이며, 신규 수집 경로의 품질 가드는 기존 ingest/repository 정책과 병행 적용됨.

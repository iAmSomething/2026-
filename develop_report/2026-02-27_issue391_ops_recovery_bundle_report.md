# 2026-02-27 Issue #391 운영 복구 runbook 자동화 스크립트 보고서

## 1. 작업 개요
- 이슈: #391 `[W8][DEVELOP][P2] 운영 복구 runbook 자동화 스크립트`
- 목표: 운영 복구 절차(ingest 재실행/단건 재처리/검증 캡처)를 단일 CLI로 자동화

## 2. 구현 내용

### 2.1 운영 복구 번들 스크립트 추가
- 파일: `scripts/qa/run_ops_recovery_bundle.py`
- 핵심 기능:
  1. ingest 재실행 단계
  - 내부적으로 `scripts/qa/run_ingest_with_retry.py` 실행 명령을 구성
  2. 특정 매치업 재처리 단계
  - 내부적으로 `scripts/qa/reprocess_single_matchup.py` 실행 명령을 구성
  3. 검증 캡처 단계
  - `/health`, `/api/v1/dashboard/summary`, `/api/v1/matchups/{matchup_id}` 응답 캡처
  4. 리포트 출력
  - 단계별 status/exit_code/output_path/error + 운영 체크리스트를 JSON으로 저장
- 지원 모드:
  - `--mode dry-run` (실행 없이 계획/체크리스트 출력)
  - `--mode apply` (실행)
- 운영 제어:
  - `--continue-on-error`
  - `--skip-ingest`, `--skip-reprocess`, `--skip-capture`

### 2.2 실패 시 롤백/재시도 가이드 자동화
- 스크립트 내 `build_ops_checklist`에서 실패 단계별 가이드 자동 추가
  - ingest 실패: retry-guide(backoff/timeout 조정 + artifact 확인)
  - reprocess 실패: rollback-guide(dry-run 재검증)
  - capture 실패: rollback-guide(health부터 순차 복구)

### 2.3 runbook 문서 반영
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 신규 섹션 `7.3 운영 복구 번들 CLI (Issue #391)` 추가
  - dry-run/apply 실행 예시
  - 산출물 목록
  - 자동 체크리스트 항목

### 2.4 테스트 추가
- 파일: `tests/test_ops_recovery_bundle_script.py`
- 검증 항목:
  - dry-run에서 단계 상태가 `planned`로 출력되는지
  - apply 실패 시 retry/rollback 가이드가 체크리스트에 포함되는지

## 3. 실행 검증
- 테스트:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_ops_recovery_bundle_script.py tests/test_reprocess_single_matchup_script.py`
  - 결과: `6 passed`
- 스크립트 smoke(dry-run):
  - `python3 scripts/qa/run_ops_recovery_bundle.py --mode dry-run --matchup-id "20260603|광역자치단체장|11-000" --output-dir /tmp/ops_bundle_demo --report /tmp/ops_bundle_demo/report.json`
  - 결과: 단계 3개(`ingest/reprocess/capture`)가 `planned`로 출력되고 report 생성 확인

## 4. 수용기준 대응
1. 복구 절차 실행시간 단축
- 단일 명령으로 ingest/reprocess/capture를 연쇄 실행 가능

2. 문서-실행 절차 일치
- runbook(7.3)에 실행 예시/산출물/체크리스트를 동기 반영

3. QA 모의 시나리오 PASS 준비
- dry-run/apply 모두 테스트 가능 구조 + 실패 가이드 자동 출력

## 5. 변경 파일
- `scripts/qa/run_ops_recovery_bundle.py`
- `tests/test_ops_recovery_bundle_script.py`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`

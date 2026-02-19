# 2026-02-19 PM Cycle QA FAIL Detection Fix Report

## 1) 이슈
- 대상: `#58 [AUTO][QA FAIL] 2026-02-18_qa_week3_integrated_gate_report`
- Report-Path: `develop_report/2026-02-19_pm_cycle_qafail_detection_fix_report.md`

## 2) 문제
- PM Cycle의 QA FAIL 탐지가 단순 문자열 포함 기준이라,
- PASS 보고서 안의 안내문구(`[QA PASS] / [QA FAIL]`)도 FAIL 보고서로 오탐됨.
- 결과적으로 불필요한 AUTO follow-up 이슈가 생성됨.

## 3) 수정 내용
1. 엄격 QA FAIL 탐지기 추가
- 파일: `scripts/pm/qafail_detection.py` (신규)
- 규칙: 줄 시작/단독 토큰 기반으로만 FAIL 판정
  - `[QA FAIL]` 단독 줄
  - `Status: FAIL`, `Verdict: FAIL`
  - `판정: FAIL`, `결론: Done 처리 불가`

2. PM Cycle 적용
- 파일: `scripts/pm/pm_cycle_dry_run.sh`
- 변경: `is_qa_fail_report()`에서 단순 grep 제거 후 `qafail_detection.py` 호출

3. 회귀 테스트 추가
- 파일: `tests/test_pm_cycle_qafail_detection.py` (신규)
- 케이스:
  - 실제 FAIL 헤더/상태 라인 인식
  - 안내문구(`[QA PASS] / [QA FAIL]`) 오탐 방지

4. 운영 문서 반영
- 파일: `docs/07_GITHUB_CLI_COLLAB_WORKFLOW.md`
- 추가: `6-3) QA FAIL 자동탐지 표준 포맷`

## 4) 검증
1. 정적 검증
- `python3 -m py_compile scripts/pm/qafail_detection.py` 통과
- `bash -n scripts/pm/pm_cycle_dry_run.sh` 통과

2. 테스트
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_pm_cycle_qafail_detection.py tests/test_pm_cycle_qapass_detection.py`
- 결과: `6 passed`

## 5) 기대 효과
- PASS 보고서의 템플릿/가이드 문구로 인한 QA FAIL 자동 이슈 오탐을 차단
- 실제 FAIL 보고서만 후속 이슈 생성 대상으로 유지

# QA Flaky 실패 탐지 및 재시도 정책 수립 보고서

- Date: 2026-02-18
- Issue: #37
- Status: PASS
- Report-Path: `QA_reports/2026-02-18_qa_flaky_detection_policy_report.md`

## 1) 최근 실행 패턴 수집(최근 20회 창)
- 수집 도구: `scripts/qa/analyze_flaky_runs.py`
- 실행 명령:
```bash
scripts/qa/analyze_flaky_runs.py --repo iAmSomething/2026- --limit 20 --output data/qa_flaky_detection_report.json
```
- 실제 수집량: 18 runs
- 요약:
  - success: 11
  - failure: 7
  - failure_rate: 38.89%

워크플로/이벤트 별:
- `Phase1 QA::workflow_dispatch` -> success 1 / failure 3
- `Staging Smoke::workflow_dispatch` -> success 6 / failure 3
- `Staging Smoke::push` -> success 2 / failure 1

## 2) flaky 의심 탐지 결과
- failed step top3:
  1. `Run Phase1 QA (manual)` 3회
  2. `Apply schema and seed sample payload` 3회
  3. `Preflight required secrets (staging)` 1회

- flaky 의심(run 복구 기반): 7건
- high-confidence(same SHA 재현 후 회복): 0건
- medium-confidence(post-change 회복): 7건

판단:
- 이번 창에서는 동일 SHA 기반 고신뢰 flaky 패턴은 확인되지 않았고,
  수정 커밋 이후 회복된 케이스가 대부분이어서 "실제 결함 수정" 비중이 높다.

## 3) 재시도 정책 vs fail-fast 기준
- 문서 반영: `docs/10_QA_WEEK3_INTEGRATED_GATE.md`

재시도(1회) 허용:
- `flake/infra`
- `flake/timing`

즉시 fail-fast:
- 계약/스키마 불일치
- 인증/시크릿 누락
- DB 부트스트랩 불가

승격 규칙:
- 동일 head SHA에서 동일 실패 2회 연속이면 flaky 해제 후 실제 결함으로 승격

## 4) QA 보고서 flaky 섹션 표준 반영
- `docs/10_QA_WEEK3_INTEGRATED_GATE.md`에 `Flaky` 섹션 템플릿 추가
- 필수 필드:
  - `flake_count`
  - `suspect_cases(run_id/failed_step/recovery_link)`
  - `retry_applied_count`
  - `escalated_real_fail_count`

## 5) 산출물
- 분석 스크립트: `scripts/qa/analyze_flaky_runs.py`
- 분석 리포트(JSON): `data/qa_flaky_detection_report.json`
- 정책/표준 문서: `docs/10_QA_WEEK3_INTEGRATED_GATE.md`
- 본 QA 보고서: `QA_reports/2026-02-18_qa_flaky_detection_policy_report.md`

## 6) 게이트 판정
- [QA PASS]
- #37 완료기준 충족:
  - flaky 탐지 리포트 1건
  - 재시도/차단 정책 문서화
  - QA 보고서 제출

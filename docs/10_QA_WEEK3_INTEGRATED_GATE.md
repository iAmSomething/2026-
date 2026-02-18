# Week3 QA 통합 회귀 게이트 규격

## 1. 목적
- UI(검색/지도/후보) + API + ingest 경로를 단일 게이트로 검증한다.
- Nightly 기준으로 회귀 리스크를 조기 탐지한다.

## 2. 통합 시나리오
1. API 계약 회귀
- 스위트: `scripts/qa/run_api_contract_suite.sh`
- 범주: success / empty / auth_failure / failure

2. Staging Smoke E2E
- 워크플로: `.github/workflows/staging-smoke.yml`
- 검증: API health, ingest job, summary/search/candidate 계약, web home 응답

3. 통합 게이트 조합
- 스크립트: `scripts/qa/run_week3_integrated_gate.sh`
- 출력:
  - `data/qa_week3_integrated_report.json`
  - `data/qa_week3_integrated_summary.md`

## 3. Nightly 절차 설계
1. `QA API Contract Suite` 실행
2. `Staging Smoke` 실행(`workflow_dispatch` 또는 push 결과 확인)
3. `run_week3_integrated_gate.sh`로 통합 판정 생성
4. QA 보고서에 PASS/FAIL 코멘트 규격대로 반영

## 4. Flaky 분류 규칙
- `flake/infra`: 네트워크, 패키지 레지스트리, 외부 서비스 가용성
- `flake/timing`: readiness race, timeout 경계
- `flake/data`: 테스트 데이터 비결정성
- `flake/test`: assertion/fixture 설계 결함

처리 기준:
1. 동일 케이스 3회 중 2회 이상 실패면 실제 결함 우선
2. 1회 실패/2회 성공이면 flake로 분류하고 원인 태깅
3. flake는 리포트에서 PASS와 별도로 누적 관리

## 5. PASS/FAIL 코멘트 규격
```md
[QA PASS]
- Scope:
- Evidence:
  - report:
  - run links:
- Gate:
```

```md
[QA FAIL]
- Scope:
- Reproduction:
- Expected:
- Actual:
- Root Cause:
- Re-assignment:
- Evidence:
```

## 6. QA 보고서 자동 요약 포맷
- 생성기: `scripts/qa/generate_week3_qa_summary.py`
- 출력 예:
  - Overall PASS/FAIL
  - API total/pass/fail
  - Staging manual/auto 결과 및 링크
  - Gate decision

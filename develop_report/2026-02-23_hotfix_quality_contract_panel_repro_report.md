# 2026-02-23 hotfix quality contract panel repro report

## 1. 요약
- 이슈: `#199 [DEVELOP][HOTFIX] 품질 API 계약/품질패널 노출/증빙 재현성 복구`
- 목표: QA 차단 원인인 품질 API 계약 필드 불일치, 홈 품질패널 미노출, #178 증빙 파일 재현성 문제를 일괄 복구

## 2. 구현
1. `/api/v1/dashboard/quality` 계약 v2 확장
- 파일: `app/models/schemas.py`, `app/services/repository.py`, `app/api/routes.py`
- 기존 하위호환 필드 유지:
  - `freshness_p50_hours`, `freshness_p90_hours`
  - `official_confirmed_ratio`
  - `needs_manual_review_count`
  - `source_channel_mix`
- 신규/강화 필드 추가:
  - `quality_status`
  - `freshness.{p50_hours,p90_hours,over_24h_ratio,over_48h_ratio,status}`
  - `official_confirmation.{confirmed_ratio,unconfirmed_count,status}`
  - `review_queue.{pending_count,in_progress_count,pending_over_24h_count}`
- 상태 계산 규칙(healthy/warn/critical) 적용:
  - freshness 지연 비율/백분위 기반
  - 공식확정 비율 기반
  - 검수대기 backlog 기반

2. 홈 품질패널 노출 보장
- 파일: `apps/web/app/page.js`, `apps/web/app/globals.css`
- `/api/v1/dashboard/quality`를 홈에서 조회하고 패널 렌더링 추가
- 키워드 고정 노출:
  - `운영 품질`
  - `신선도`
  - `공식확정 비율`
  - `검수대기`

3. QA/재현성 스크립트 보강
- 파일: `scripts/qa/run_api_contract_suite.sh`
  - quality success/empty/failure 케이스 추가
- 파일: `scripts/qa/check_phase1.sh`
  - `--with-api` 시 quality 계약 검증 추가

4. #178 증빙 재현성 복구
- 파일: `develop_report/2026-02-22_W2_UI_명세와_API_응답_계약_불일치_제거_report.md`
- 조치:
  - 증빙 경로를 추적 가능한 `data/verification/*`로 정리
  - `issue178_api_contract_report.json`/digest를 저장소에 재생성해 재현 가능 상태로 고정

5. 문서 계약 동기화
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - quality v2 확장 필드 규칙 반영
- 파일: `docs/03_UI_UX_SPEC.md`
  - 운영 품질 패널 필수 필드 목록 갱신
- 파일: `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - 운영 확인 항목에 v2 필드 추가

## 3. 검증
1. API/웹 키워드 회귀 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_api_routes.py tests/test_web_quality_panel_keywords.py`
- 결과: `11 passed`

2. API 계약 스위트
- 명령: `bash scripts/qa/run_api_contract_suite.sh --report data/verification/issue199_api_contract_report.json`
- 결과: `total=31, pass=31, fail=0`

3. #178 증빙 재현성 재생성
- 명령: `bash scripts/qa/run_api_contract_suite.sh --report data/verification/issue178_api_contract_report.json`
- 결과: `total=31, pass=31, fail=0`

## 4. 증빙 파일
- `data/verification/issue199_quality_hotfix_pytest.log`
- `data/verification/issue199_quality_hotfix_contract_suite.log`
- `data/verification/issue199_dashboard_quality_sample.json`
- `data/verification/issue199_api_contract_report.json`
- `data/verification/issue199_api_contract_report_digest.json`
- `data/verification/issue178_api_contract_report.json`
- `data/verification/issue178_api_contract_report_digest.json`

## 5. DoD 체크
- [x] 구현/테스트/증빙 반영
- [x] report_path/evidence/next_status 코멘트 준비
- [x] 재게이트에서 QA PASS 확보 근거(계약 스위트/키워드 테스트) 확보

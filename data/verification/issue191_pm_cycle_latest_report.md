# PM Cycle Dry Run
- generated_at_utc: 2026-02-23T04:31:34Z
- repo: iAmSomething/2026-
- report_date_filter: (none)
- mode: dry-run

## Snapshot
- total_issues: 153
- closed_issues: 139
- open_issues: 14
- blocked_open_issues: 3
- ready_open_issues: 0

## Open By Role
- role/uiux: 2
- role/collector: 5
- role/develop: 2
- role/qa: 5

## Label Health
- role/qa label: yes
- status/in-qa label: yes

## Secret Health (Review)
- status: ok
- missing_required_secrets: 0

## Open Issue Queue
- [#200](https://github.com/iAmSomething/2026-/issues/200) [COLLECTOR][HOTFIX] freshness p90 임계치(<=96h) 복구 v1 (#160/#175 unblock)
- [#193](https://github.com/iAmSomething/2026-/issues/193) [QA][W4] 4주 통합 릴리즈 게이트(기능/데이터/시각)
- [#192](https://github.com/iAmSomething/2026-/issues/192) [UIUX][W4] 대시보드 프로덕션 시각 베이스라인 v2
- [#191](https://github.com/iAmSomething/2026-/issues/191) [DEVELOP][W4] PM Cycle 자동화 회귀 테스트팩 확장
- [#189](https://github.com/iAmSomething/2026-/issues/189) [COLLECTOR][W4] low-confidence triage 정책 자동 라우팅
- [#188](https://github.com/iAmSomething/2026-/issues/188) [COLLECTOR][W4] 30일 커버리지 자동 확장 배치 v2
- [#187](https://github.com/iAmSomething/2026-/issues/187) [QA][W3] 스코프 오염 방지 회귀게이트
- [#186](https://github.com/iAmSomething/2026-/issues/186) [UIUX][W3] 전국 vs 지역 여론 분리 시각화 강화
- [#185](https://github.com/iAmSomething/2026-/issues/185) [DEVELOP][W3] region search 한글/인코딩 호환성 하드닝
- [#183](https://github.com/iAmSomething/2026-/issues/183) [COLLECTOR][W3] NESDC PDF 템플릿 어댑터 확장(기관 5종)
- [#182](https://github.com/iAmSomething/2026-/issues/182) [COLLECTOR][W3] 정당 미기재 후보 소속 추정 v2
- [#181](https://github.com/iAmSomething/2026-/issues/181) [QA][W2] API-UI 필드명 불일치 제로 게이트
- [#175](https://github.com/iAmSomething/2026-/issues/175) [QA][W1] 운영 안정화 게이트 v2(품질패널+API)
- [#160](https://github.com/iAmSomething/2026-/issues/160) [QA] 운영 안정화 게이트 v1 (quality API + UI 패널 + 기존 스모크)

## Latest Reports
- UIUX_reports: `UIUX_reports/2026-02-19_uiux_issue38_geojson_map_a11y_regression_report.md`
- Collector_reports: `Collector_reports/2026-02-19_collector_weekly_domain_quality_template_report.md`
- develop_report: `develop_report/2026-02-23_hotfix_quality_contract_panel_repro_report.md`
- QA_reports: `QA_reports/2026-02-18_qa_week3_integrated_gate_report.md`

## QA Reassignment Hints
- `QA_reports/2026-02-18_qa_api_contract_suite_report.md`: root_cause=`QA_reports/2026-02-18_qa_api_contract_suite_report.md`, suggested_reassign=`role/develop`
- `QA_reports/2026-02-18_qa_flaky_detection_policy_report.md`: root_cause=`QA_reports/2026-02-18_qa_flaky_detection_policy_report.md`, suggested_reassign=`role/develop`
- `QA_reports/2026-02-18_qa_staging_smoke_db_report.md`: root_cause=`QA_reports/2026-02-18_qa_staging_smoke_db_report.md`, suggested_reassign=`role/develop`
- `QA_reports/2026-02-18_qa_week1_audit_report.md`: root_cause=`QA_reports/2026-02-18_qa_week1_audit_report.md`, suggested_reassign=`role/develop`
- `QA_reports/2026-02-18_qa_week3_integrated_gate_report.md`: root_cause=`QA_reports/2026-02-18_qa_week3_integrated_gate_report.md`, suggested_reassign=`role/develop`

## Gate Checks
- reopen_policy_enabled: false
- reopen_lookback_days: 7
- reopen_candidates_checked: 0
- closed+done without [QA PASS]: 0

## Applied Actions
- (none)

## Suggested Next Actions
1. blocked 이슈 우선 해소 후 ready 이슈 순차 진행
2. QA FAIL 보고서는 auto_key 기반 중복 없이 후속 이슈 생성
3. done 이슈 자동 재오픈은 PM_CYCLE_ALLOW_REOPEN_DONE=true 를 명시한 단발성 apply에서만 사용

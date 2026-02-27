[DEVELOP][INGEST FAILURE TEMPLATE]
report_path: develop_report/YYYY-MM-DD_issueNNN_ingest_failure_report.md
evidence:
- workflow_run: https://github.com/iAmSomething/2026-/actions/runs/22467650760
- ingest_report: `data/ingest_schedule_report.json`
- classification_artifact: `data/ingest_schedule_failure_classification.json`
- dead_letter: `data/dead_letter/ingest_dead_letter_20260227T005641Z_timeout.json`
- failure_class: `timeout`
- failure_type: `timeout`
- cause_code: `timeout_request`
- failure_reason: `timeout: ReadTimeout: timed out`
next_status: status/in-progress

# Summary
1. cause_code 기반으로 DB/Auth/Schema/Timeout 조치 대상을 분리합니다.
2. 동일 유형 재실행에서 cause_code 일치 여부를 확인합니다.

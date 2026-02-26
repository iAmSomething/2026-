[DEVELOP][INGEST FAILURE TEMPLATE]
report_path: develop_report/YYYY-MM-DD_issueNNN_ingest_failure_report.md
evidence:
- workflow_run: https://github.com/iAmSomething/2026-/actions/runs/22444570489
- ingest_report: `data/ingest_schedule_report.json`
- classification_artifact: `data/ingest_schedule_failure_classification.json`
- dead_letter: `data/dead_letter/ingest_dead_letter_20260226T133930Z_http_5xx.json`
- failure_class: `http_5xx`
- failure_type: `http_5xx`
- cause_code: `db_connection_unknown`
- failure_reason: `http_5xx: http_status=503 (database connection failed (unknown))`
next_status: status/in-progress

# Summary
1. cause_code 기반으로 DB/Auth/Schema/Timeout 조치 대상을 분리합니다.
2. 동일 유형 재실행에서 cause_code 일치 여부를 확인합니다.

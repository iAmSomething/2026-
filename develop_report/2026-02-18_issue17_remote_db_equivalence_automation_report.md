# 이슈 #17 보고서: Supabase 원격DB 동등성 검증 시나리오 자동화

- 이슈: https://github.com/iAmSomething/2026-/issues/17
- 작성일: 2026-02-18
- 담당: develop

## 1. 구현 사항
1. 원격/로컬 공용 자동검증 스크립트 구현
- 파일: `scripts/qa/run_db_equivalence.py`
- 기능:
  - 스키마 적용
  - 수동 적재 2회(idempotent) 검증
  - DB 무결성 체크
  - API 3개 계약 체크(summary/regions/candidate)
  - 실패 시 원인 분류(`schema`, `permission`, `data`, `network`)

2. 원격 환경 충돌 대응
- 옵션: `--remote-isolated-db` / `--no-remote-isolated-db`
- 기존 원격 테이블 스키마 충돌 상황을 분리 실행으로 대응 가능하게 개선

## 2. 실행 결과 (원격 성공)
1. 실행 커맨드
```bash
.venv/bin/python scripts/qa/run_db_equivalence.py \
  --target remote \
  --no-remote-isolated-db \
  --report data/qa_remote_db_report.json
```

2. 결과
- `status: success`
- `ingest_first_run.run_id: 1`
- `ingest_second_run.run_id: 2`
- `db_checks.counts.ingestion_runs: 2`
- `api_checks.status: ok`

3. 산출물
- `data/qa_remote_db_report.json`

## 3. 변경 파일
1. `scripts/qa/run_db_equivalence.py`
2. `data/qa_remote_db_report.json`
3. `develop_report/2026-02-18_issue17_remote_db_equivalence_automation_report.md`

## 4. 결론
- 이슈 #17 완료기준 충족
  - 원격 DB 기준 재현 성공 로그 확보
  - develop 보고서 제출 완료

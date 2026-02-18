# 이슈 #17 보고서: Supabase 원격DB 동등성 검증 시나리오 자동화

- 이슈: https://github.com/iAmSomething/2026-/issues/17
- 작성일: 2026-02-18
- 담당: develop

## 1. 구현 사항
1. 공용 자동검증 스크립트 추가
- 파일: `scripts/qa/run_db_equivalence.py`
- 대상 분기: `--target local | remote`
- 입력: `--input`(기본 `data/sample_ingest.json`)
- 출력 리포트: `--report` (권장 `data/qa_local_db_report.json`, `data/qa_remote_db_report.json`)

2. 자동검증 시나리오 포함 항목
- 스키마 적용
- 수동 적재 2회 실행(idempotent)
- DB 무결성/정규화 체크
- API 3개 계약 체크(summary/regions/candidate)
- 실패 원인 분류(`schema`, `permission`, `data`, `network`) + JSON 보고서 저장

3. README 반영
- 로컬/원격 실행 커맨드 추가

## 2. 실행 검증 결과
1. 로컬 실행 성공
- 명령: `DATABASE_URL=postgresql://gimtaehun@localhost:5432/election2026_dev .venv/bin/python scripts/qa/run_db_equivalence.py --target local --report data/qa_local_db_report.json`
- 결과: `{"status":"success","report":"data/qa_local_db_report.json"}`

2. 산출 리포트
- `data/qa_local_db_report.json` 생성 확인
- 단계별 성공 로그(스키마/적재2회/DB체크/API3체크) 포함

## 3. 상태
- 자동화 구현은 완료
- 원격 DB 성공 로그 생성은 `#7`(service_role rotate/secret 재주입) 완료 후 실행 가능

## 4. 변경 파일
- `scripts/qa/run_db_equivalence.py`
- `README.md`

## 5. 결론
- 구현/문서/로컬 테스트 반영 완료
- 원격 DB 최종 성공 로그는 선행 이슈 #7 완료 후 후속 1회 실행으로 마감 가능

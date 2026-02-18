# 이슈 #6 보고서: 수동 적재 1회 실DB 검증 + API 3개 계약 대조

- 이슈: https://github.com/iAmSomething/2026-/issues/6
- 작성일: 2026-02-18
- 담당: develop

## 1. 수행 범위
1. 실DB(로컬 PostgreSQL) 대상 수동 적재 1회 실행
2. 재적재 시 idempotent 유지 확인
3. API 3개 응답 샘플을 문서 계약과 대조

## 2. 실행 환경
1. Python: `.venv` / 3.13.5
2. DB: `postgresql://gimtaehun@localhost:5432/election2026_dev`
3. 입력 데이터: `data/sample_ingest.json`

## 3. 검증 로그
1. 수동 적재 1회 실행 결과
- `run_id=3`
- `processed_count=1`
- `error_count=0`
- `status=success`

2. idempotent 확인(SQL 카운트)
- `articles=1`
- `poll_observations=1`
- `poll_options=3`
- `ingestion_runs=3` (실행 이력만 증가)

## 4. API 3개 응답 샘플
1. `GET /api/v1/dashboard/summary`
```json
{"as_of":null,"party_support":[],"presidential_approval":[{"option_name":"국정안정론","value_mid":54.0,"pollster":"MBC","survey_end_date":"2026-02-18","verified":true}]}
```

2. `GET /api/v1/regions/search?q=서울`
```json
[{"region_code":"11-000","sido_name":"서울특별시","sigungu_name":"전체","admin_level":"sido"}]
```

3. `GET /api/v1/candidates/cand-jwo`
```json
{"candidate_id":"cand-jwo","name_ko":"정원오","party_name":"더불어민주당","gender":"M","birth_date":"1968-08-12","job":"구청장","career_summary":"성동구청장","election_history":"지방선거 출마"}
```

## 5. 계약 대조 결과
1. 대조 기준
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`

2. 결과
- 3개 API의 필수 필드(`option_name`, `value_mid`, `pollster`, `survey_end_date`, `verified`, `region_code`, `sido_name`, `sigungu_name`, `candidate_id`, `name_ko`, `party_name`, `career_summary`) 응답 확인
- 필드명 `snake_case` 일치 확인

## 6. 결론
- 이슈 #6 DoD 충족(구현/문서/테스트 반영 + 보고서 제출)
